"""
Course publisher views.
"""
import json
import logging
from datetime import datetime, timedelta
from functools import reduce

import waffle
from django.contrib import messages
from django.contrib.sites.models import Site
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import Count, Q
from django.db.models.functions import Lower
from django.forms import model_to_dict
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView, View
from guardian.shortcuts import get_objects_for_user

from course_discovery.apps.core.models import User
from course_discovery.apps.course_metadata.models import Person
from course_discovery.apps.ietf_language_tags.models import LanguageTag
from course_discovery.apps.publisher import emails, mixins, serializers
from course_discovery.apps.publisher.choices import CourseRunStateChoices, CourseStateChoices, PublisherUserRole
from course_discovery.apps.publisher.dataloader.create_courses import process_course
from course_discovery.apps.publisher.emails import send_email_for_published_course_run_editing
from course_discovery.apps.publisher.forms import (AdminImportCourseForm, CourseForm, CourseRunForm, CourseSearchForm,
                                                   SeatForm)
from course_discovery.apps.publisher.models import (Course, CourseRun, CourseRunState, CourseState, CourseUserRole,
                                                    OrganizationExtension, Seat, UserAttributes)
from course_discovery.apps.publisher.utils import (get_internal_users, has_role_for_course, is_internal_user,
                                                   is_project_coordinator_user, is_publisher_admin, make_bread_crumbs)
from course_discovery.apps.publisher.wrappers import CourseRunWrapper

logger = logging.getLogger(__name__)

ROLE_WIDGET_HEADINGS = {
    PublisherUserRole.PartnerManager: _('PARTNER MANAGER'),
    PublisherUserRole.ProjectCoordinator: _('PROJECT COORDINATOR'),
    PublisherUserRole.MarketingReviewer: _('MARKETING'),
    PublisherUserRole.Publisher: _('PUBLISHER'),
    PublisherUserRole.CourseTeam: _('COURSE TEAM')
}

STATE_BUTTONS = {
    CourseStateChoices.Draft: {'text': _('Send for Review'), 'value': CourseStateChoices.Review},
    CourseStateChoices.Review: {'text': _('Mark as Reviewed'), 'value': CourseStateChoices.Approved}
}

DEFAULT_ROLES = [
    PublisherUserRole.MarketingReviewer, PublisherUserRole.ProjectCoordinator, PublisherUserRole.Publisher
]

COURSE_ROLES = [PublisherUserRole.CourseTeam]
COURSE_ROLES.extend(DEFAULT_ROLES)

COURSES_DEFAULT_PAGE_SIZE = 25
COURSES_ALLOWED_PAGE_SIZES = (25, 50, 100)

EDX_STATUS_COLUMN_INDEX = 6
COURSE_RUNS_COUNT_INDEX = 3


class CourseRunListView(mixins.LoginRequiredMixin, ListView):
    default_published_days = 30

    def get_queryset(self):
        """ On dashboard courses are divided in multiple categories.
        Publisher admin can view all these courses.
        Internal users can see the assigned courses with roles only.
        Users can see the courses if they are part of any group and that group has associated
        with any organization and organization is part of a course and permissions are assigned
        to the organization
        """
        user = self.request.user
        if is_publisher_admin(user):
            course_runs = CourseRun.objects.select_related('course').all()
        elif is_internal_user(user):
            internal_user_courses = Course.objects.filter(course_user_roles__user=user)
            course_runs = CourseRun.objects.filter(course__in=internal_user_courses).select_related('course').all()
        else:
            organizations = get_objects_for_user(
                user, OrganizationExtension.VIEW_COURSE, OrganizationExtension,
                use_groups=True,
                with_superuser=False
            ).values_list('organization')
            course_runs = CourseRun.objects.filter(
                course__organizations__in=organizations
            ).select_related('course').all()

        return course_runs

    def get_context_data(self, **kwargs):
        """ Courses lists are further divided into different categories."""
        context = super(CourseRunListView, self).get_context_data(**kwargs)
        course_runs = context.get('object_list')
        published_course_runs = course_runs.filter(
            course_run_state__name=CourseRunStateChoices.Published,
            course_run_state__modified__gt=datetime.today() - timedelta(days=self.default_published_days)
        ).select_related('course_run_state').order_by('-course_run_state__modified')

        unpublished_course_runs = course_runs.exclude(course_run_state__name=CourseRunStateChoices.Published)

        # Studio requests needs to check depending upon the user role with course
        # Also user should be part of project coordinator group.
        if is_publisher_admin(self.request.user):
            studio_request_courses = unpublished_course_runs.filter(lms_course_id__isnull=True)
        elif is_project_coordinator_user(self.request.user):
            studio_request_courses = unpublished_course_runs.filter(lms_course_id__isnull=True).filter(
                course__course_user_roles__role=PublisherUserRole.ProjectCoordinator
            )
        else:
            studio_request_courses = []

        context['studio_request_courses'] = CourseRunWrapper.get_course_run_wrappers(studio_request_courses)
        context['unpublished_course_runs'] = CourseRunWrapper.get_course_run_wrappers(unpublished_course_runs)
        context['published_course_runs'] = CourseRunWrapper.get_course_run_wrappers(published_course_runs)
        context['default_published_days'] = self.default_published_days

        in_progress_course_runs = course_runs.filter(
            course_run_state__name__in=[CourseRunStateChoices.Review, CourseRunStateChoices.Draft]
        ).select_related('course_run_state').order_by('-course_run_state__modified')

        preview_course_runs = unpublished_course_runs.filter(
            course_run_state__name=CourseRunStateChoices.Approved,
        ).order_by('-course_run_state__modified')

        context['in_progress_course_runs'] = CourseRunWrapper.get_course_run_wrappers(in_progress_course_runs)
        context['preview_course_runs'] = CourseRunWrapper.get_course_run_wrappers(preview_course_runs)

        # shows 'studio request' tab only to project coordinators
        context['is_project_coordinator'] = is_project_coordinator_user(self.request.user)

        site = Site.objects.first()
        context['site_name'] = 'edX' if 'edx' in site.name.lower() else site.name

        context['course_team_status'] = '{}|{}'.format(
            CourseRunWrapper.Draft, CourseRunWrapper.AwaitingCourseTeamReview
        )
        context['course_team_count'] = in_progress_course_runs.filter(
            course_run_state__owner_role=PublisherUserRole.CourseTeam
        ).count()

        context['internal_user_status'] = CourseRunWrapper.AwaitingProjectCoordinatorReview
        context['internal_user_count'] = in_progress_course_runs.exclude(
            course_run_state__owner_role=PublisherUserRole.CourseTeam
        ).count()

        return context


class CourseRunDetailView(mixins.LoginRequiredMixin, mixins.PublisherPermissionMixin, DetailView):
    """ Course Run Detail View."""
    model = CourseRun
    template_name = 'publisher/course_run_detail/course_run_detail.html'
    permission = OrganizationExtension.VIEW_COURSE_RUN

    def get_context_data(self, **kwargs):
        context = super(CourseRunDetailView, self).get_context_data(**kwargs)

        user = self.request.user
        course_run = CourseRunWrapper(self.get_object())

        context['object'] = course_run
        context['comment_object'] = course_run

        # this URL is used for the comments post back redirection.
        context['post_back_url'] = reverse('publisher:publisher_course_run_detail', kwargs={'pk': course_run.id})

        context['can_edit'] = mixins.check_course_organization_permission(
            user, course_run.course, OrganizationExtension.EDIT_COURSE_RUN
        ) and has_role_for_course(course_run.course, user)

        context['role_widgets'] = get_course_role_widgets_data(
            user, course_run.course, course_run.course_run_state, 'publisher:api:change_course_run_state'
        )
        course_run_state = course_run.course_run_state
        if course_run_state.preview_accepted:
            history_object = course_run_state.history.filter(preview_accepted=True).order_by('-modified').first()
            if history_object:
                context['preview_accepted_date'] = history_object.modified
        if course_run_state.is_published:
            history_object = course_run_state.history.filter(
                name=CourseRunStateChoices.Published
            ).order_by('-modified').first()
            if history_object:
                context['publish_date'] = history_object.modified

        start_date = course_run.start.strftime("%B %d, %Y") if course_run.start else None
        context['breadcrumbs'] = make_bread_crumbs(
            [
                (reverse('publisher:publisher_courses'), _('Courses')),
                (
                    reverse('publisher:publisher_course_detail', kwargs={'pk': course_run.course.id}),
                    '{number}: {title}'.format(number=course_run.course.number, title=course_run.course.title)
                ),
                (None, '{type}: {start}'.format(
                    type=course_run.get_pacing_type_display(), start=start_date
                ))
            ]
        )

        context['can_view_all_tabs'] = mixins.check_roles_access(user)
        context['publisher_hide_features_for_pilot'] = waffle.switch_is_active('publisher_hide_features_for_pilot')
        context['publisher_comment_widget_feature'] = waffle.switch_is_active('publisher_comment_widget_feature')
        context['publisher_approval_widget_feature'] = waffle.switch_is_active('publisher_approval_widget_feature')
        context['publish_state_name'] = CourseRunStateChoices.Published

        context['course_staff_config'] = json.dumps({
            staff['uuid']: staff
            for staff in course_run.course_staff
        })

        if context['can_edit'] and not waffle.switch_is_active('disable_publisher_permissions'):
            current_owner_role = course_run.course.course_user_roles.get(role=course_run.course_run_state.owner_role)
            user_role = course_run.course.get_user_role(user=user)
            if user_role != current_owner_role.role:
                context['add_warning_popup'] = True
                context['current_team_name'] = (_('course team')
                                                if current_owner_role.role == PublisherUserRole.CourseTeam
                                                else _('project coordinator'))
                context['team_name'] = (_('course team')
                                        if current_owner_role.role == PublisherUserRole.ProjectCoordinator
                                        else _('project coordinator'))

        return context


# pylint: disable=attribute-defined-outside-init
class CreateCourseView(mixins.LoginRequiredMixin, mixins.PublisherUserRequiredMixin, CreateView):
    """ Create Course View."""
    model = Course
    course_form = CourseForm
    template_name = 'publisher/add_course_form.html'
    success_url = 'publisher:publisher_course_detail'

    def get_success_url(self, course_id, add_new_run=None):  # pylint: disable=arguments-differ
        success_url = reverse(self.success_url, kwargs={'pk': course_id})
        if add_new_run:
            success_url = reverse('publisher:publisher_course_runs_new', kwargs={'parent_course_id': course_id})
        return success_url

    def get_context_data(self):
        return {
            'course_form': self.course_form(user=self.request.user),
            'publisher_hide_features_for_pilot': waffle.switch_is_active('publisher_hide_features_for_pilot'),
            'publisher_add_instructor_feature': waffle.switch_is_active('publisher_add_instructor_feature'),
        }

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context_data())

    def post(self, request, *args, **kwargs):
        ctx = self.get_context_data()
        add_new_run = request.POST.get('add_new_run')

        # pass selected organization to CourseForm to populate related
        # choices into institution admin field
        user = self.request.user
        organization = self.request.POST.get('organization')

        course_form = self.course_form(
            request.POST, request.FILES, user=user, organization=organization
        )
        if course_form.is_valid():
            try:
                with transaction.atomic():
                    course = course_form.save(commit=False)
                    course.changed_by = user
                    course.save()
                    # commit false does not save m2m object. Keyword field is m2m.
                    course_form.save_m2m()

                    organization_extension = get_object_or_404(
                        OrganizationExtension, organization=course_form.data['organization']
                    )
                    course.organizations.add(organization_extension.organization)

                    # add default organization roles into course-user-roles
                    course.assign_organization_role(organization_extension.organization)

                    # add team admin as CourseTeam role again course
                    CourseUserRole.add_course_roles(course=course, role=PublisherUserRole.CourseTeam,
                                                    user=User.objects.get(id=course_form.data['team_admin']))

                    # Initialize workflow for Course.
                    CourseState.objects.create(course=course, owner_role=PublisherUserRole.CourseTeam)

                    if add_new_run:
                        # pylint: disable=no-member
                        messages.success(
                            request, _(
                                "{course_title} has been created successfully. Enter information on this page to "
                                "create a course run for this course."
                            ).format(course_title=course.title)
                        )
                    else:
                        # pylint: disable=no-member
                        messages.success(
                            request, _(
                                "You have successfully created a course. You can edit the course information or enter "
                                "information for the course About page at any time before you send the course to"
                                " edX marketing for review. "
                            )
                        )

                    return HttpResponseRedirect(self.get_success_url(course.id, add_new_run=add_new_run))
            except Exception as e:  # pylint: disable=broad-except
                # pylint: disable=no-member
                error_message = _('An error occurred while saving your changes. {error}').format(error=str(e))
                messages.error(request, error_message)

        if not messages.get_messages(request):
            messages.error(
                request, _('The page could not be updated. Make sure that all values are correct, then try again.')
            )

        if course_form.errors.get('image'):
            messages.error(request, course_form.errors.get('image'))

        ctx.update(
            {
                'course_form': course_form,
            }
        )
        return render(request, self.template_name, ctx, status=400)


class CourseEditView(mixins.PublisherPermissionMixin, UpdateView):
    """ Course Edit View."""
    model = Course
    form_class = CourseForm
    permission = OrganizationExtension.EDIT_COURSE
    template_name = 'publisher/course_edit_form.html'
    success_url = 'publisher:publisher_course_detail'

    def get_success_url(self):
        return reverse(self.success_url, kwargs={'pk': self.object.id})

    def get_form_kwargs(self):
        """
        Pass extra kwargs to form, required for team_admin and organization querysets.
        """
        kwargs = super(CourseEditView, self).get_form_kwargs()
        request = self.request

        if request.POST:
            kwargs.update(
                {'user': request.user, 'organization': request.POST.get('organization')}
            )
        else:
            organization = self.object.organizations.first()
            kwargs.update(
                user=request.user,
                organization=organization,
                initial={
                    'organization': organization,
                    'team_admin': self.object.course_team_admin
                }
            )

        return kwargs

    def get_context_data(self, **kwargs):
        context = super(CourseEditView, self).get_context_data(**kwargs)
        history_id = self.request.GET.get('history_id', None)

        try:
            history_object = self.object.history.get(history_id=history_id) if history_id else None
        except:  # pylint: disable=bare-except
            history_object = None

        context.update(
            {
                'is_internal_user': is_internal_user(self.request.user),
                'history_object': history_object
            }
        )
        return context

    def form_valid(self, form):
        """
        If the form is valid, update organization and team_admin.
        """
        user = self.request.user
        self.object = form.save(commit=False)
        self.object.changed_by = user
        self.object.save()

        organization = form.cleaned_data['organization']
        if self.object.organizations.first() != organization:
            organization_extension = get_object_or_404(OrganizationExtension, organization=organization)
            self.object.organizations.remove(self.object.organizations.first())
            self.object.organizations.add(organization_extension.organization)

        try:
            latest_run = self.object.course_runs.latest()
        except CourseRun.DoesNotExist:
            latest_run = None

        if latest_run and latest_run.course_run_state.name == CourseRunStateChoices.Published:
            # If latest run of this course is published send an email to Publisher and don't change state.
            send_email_for_published_course_run_editing(latest_run, self.request.site)
        else:
            user_role = self.object.get_user_role(user=user)
            # Change course state to draft if marketing not yet reviewed or
            # if marketing person updating the course.
            if not self.object.course_state.marketing_reviewed or user_role == PublisherUserRole.MarketingReviewer:
                if (self.object.course_state.name != CourseStateChoices.Draft and
                        user_role != PublisherUserRole.ProjectCoordinator):
                    self.object.course_state.change_state(
                        state=CourseStateChoices.Draft, user=user, site=self.request.site
                    )

                # Change ownership if user role not equal to owner role.
                if user_role not in (self.object.course_state.owner_role, PublisherUserRole.ProjectCoordinator):
                    self.object.course_state.change_owner_role(user_role)

        team_admin = form.cleaned_data['team_admin']
        if self.object.course_team_admin != team_admin:
            course_admin_role = get_object_or_404(
                CourseUserRole, course=self.object, role=PublisherUserRole.CourseTeam
            )

            course_admin_role.user = team_admin
            course_admin_role.save()

        messages.success(self.request, _('Course  updated successfully.'))
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form):
        # pylint: disable=no-member
        messages.error(
            self.request, _('The page could not be updated. Make sure that all values are correct, then try again.')
        )
        return self.render_to_response(self.get_context_data(form=form))


class CourseDetailView(mixins.LoginRequiredMixin, mixins.PublisherPermissionMixin, DetailView):
    """ Course Detail View."""
    model = Course
    template_name = 'publisher/course_detail.html'
    permission = OrganizationExtension.VIEW_COURSE

    def get_context_data(self, **kwargs):
        context = super(CourseDetailView, self).get_context_data(**kwargs)

        user = self.request.user
        course = self.object

        context['can_edit'] = mixins.check_course_organization_permission(
            user, course, OrganizationExtension.EDIT_COURSE
        ) and has_role_for_course(course, user)

        context['breadcrumbs'] = make_bread_crumbs(
            [
                (reverse('publisher:publisher_courses'), _('Courses')),
                (None, '{number}: {title}'.format(number=course.number, title=course.course_title)),
            ]
        )
        context['comment_object'] = course
        context['post_back_url'] = reverse('publisher:publisher_course_detail', kwargs={'pk': self.object.id})
        context['publisher_hide_features_for_pilot'] = waffle.switch_is_active('publisher_hide_features_for_pilot')
        context['publisher_comment_widget_feature'] = waffle.switch_is_active('publisher_comment_widget_feature')
        context['publisher_history_widget_feature'] = waffle.switch_is_active('publisher_history_widget_feature')
        context['publisher_approval_widget_feature'] = waffle.switch_is_active('publisher_approval_widget_feature')
        context['role_widgets'] = get_course_role_widgets_data(
            user, course, course.course_state, 'publisher:api:change_course_state', parent_course=True
        )

        # Add warning popup information if user can edit the course but does not own it.
        if context['can_edit'] and not waffle.switch_is_active('disable_publisher_permissions'):
            current_owner_role = course.course_user_roles.get(role=course.course_state.owner_role)
            user_role = course.get_user_role(user=user)
            if user_role != current_owner_role.role:
                context['add_warning_popup'] = True
                context['current_team_name'] = (_('course')
                                                if current_owner_role.role == PublisherUserRole.CourseTeam
                                                else _('marketing'))
                context['team_name'] = (_('course')
                                        if current_owner_role.role == PublisherUserRole.MarketingReviewer
                                        else _('marketing'))

            history_list = self.object.history.all().order_by('history_id')

            # Find out history of a logged-in user from the history list and if there is any other latest history
            # from other users then show accept changes button.
            if history_list and history_list.filter(history_user=self.request.user).exists():
                    logged_in_user_history = history_list.filter(history_user=self.request.user).latest()
                    context['most_recent_revision_id'] = (
                        logged_in_user_history.history_id if logged_in_user_history else None
                    )

                    if history_list.latest().history_id > logged_in_user_history.history_id:
                        context['accept_all_button'] = (
                            current_owner_role.role == PublisherUserRole.CourseTeam and
                            current_owner_role.user == self.request.user
                        )

        return context


class CreateCourseRunView(mixins.LoginRequiredMixin, mixins.PublisherUserRequiredMixin, CreateView):
    """ Create Course Run View."""
    model = CourseRun
    run_form = CourseRunForm
    seat_form = SeatForm
    template_name = 'publisher/add_courserun_form.html'
    success_url = 'publisher:publisher_course_run_detail'
    parent_course = None
    last_run = None
    fields = ()

    def get_parent_course(self):
        if not self.parent_course:
            self.parent_course = get_object_or_404(Course, pk=self.kwargs.get('parent_course_id'))

        return self.parent_course

    def get_last_run(self):
        if not self.last_run:
            parent_course = self.get_parent_course()
            try:
                self.last_run = parent_course.course_runs.latest('created')
            except CourseRun.DoesNotExist:
                self.last_run = None

        return self.last_run

    def set_last_run_data(self, new_run):
        last_run = self.get_last_run()
        if last_run:
            last_run_data = model_to_dict(last_run)
            # Delete all those fields which cannot be copied from previous run
            del (last_run_data['id'], last_run_data['start'], last_run_data['end'], last_run_data['pacing_type'],
                 last_run_data['preview_url'], last_run_data['lms_course_id'], last_run_data['changed_by'],
                 last_run_data['course'], last_run_data['sponsor'], last_run_data['enrollment_start'],
                 last_run_data['enrollment_end'])

            staff = Person.objects.filter(id__in=last_run_data.pop('staff'))
            transcript_languages = LanguageTag.objects.filter(code__in=last_run_data.pop('transcript_languages'))
            language_code = last_run_data.pop('language')
            if language_code:
                last_run_data['language'] = LanguageTag.objects.get(code=language_code)
            video_language_code = last_run_data.pop('video_language')
            if video_language_code:
                last_run_data['video_language'] = LanguageTag.objects.get(code=video_language_code)

            for attr, value in last_run_data.items():
                setattr(new_run, attr, value)

            new_run.save()
            new_run.staff.add(*staff)
            new_run.transcript_languages.add(*transcript_languages)

        new_run.save()

    def get_seat_initial_data(self):
        initial_seat_data = {}
        last_run = self.get_last_run()
        if not last_run:
            return initial_seat_data

        try:
            latest_seat = last_run.seats.latest('created')
            initial_seat_data = model_to_dict(latest_seat)
            del initial_seat_data['id'], initial_seat_data['course_run'], initial_seat_data['changed_by']
        except Seat.DoesNotExist:
            initial_seat_data = {}

        return initial_seat_data

    def get_context_data(self, **kwargs):
        parent_course = self.get_parent_course()
        last_run = self.get_last_run()
        run_initial_data = {}
        if last_run:
            run_initial_data = {'pacing_type': last_run.pacing_type}

        context = {
            'parent_course': parent_course,
            'run_form': self.run_form(initial=run_initial_data),
            'seat_form': self.seat_form(initial=self.get_seat_initial_data())
        }
        return context

    def post(self, request, *args, **kwargs):
        user = request.user
        parent_course = self.get_parent_course()

        run_form = self.run_form(request.POST)
        seat_form = self.seat_form(request.POST)

        if parent_course.course_user_roles.filter(role__in=COURSE_ROLES).count() == len(COURSE_ROLES) or \
                waffle.switch_is_active('disable_publisher_permissions'):

            if run_form.is_valid() and seat_form.is_valid():
                try:
                    with transaction.atomic():
                        course_run = run_form.save(commit=False, course=parent_course, changed_by=user)
                        self.set_last_run_data(course_run)
                        seat_form.save(course_run=course_run, changed_by=user)

                        # Initialize workflow for Course-run.
                        CourseRunState.objects.create(course_run=course_run, owner_role=PublisherUserRole.CourseTeam)

                        # pylint: disable=no-member
                        success_msg = _('You have successfully created a course run for {course_title}.').format(
                            course_title=parent_course.title
                        )
                        messages.success(request, success_msg)

                        emails.send_email_for_course_creation(parent_course, course_run, request.site)
                        return HttpResponseRedirect(reverse(self.success_url, kwargs={'pk': course_run.id}))
                except Exception as error:  # pylint: disable=broad-except
                    # pylint: disable=no-member
                    error_msg = _('There was an error saving this course run: {error}').format(error=error)
                    messages.error(request, error_msg)
                    logger.exception('Unable to create course run and seat for course [%s].', parent_course.id)
            else:
                messages.error(
                    request, _('The page could not be updated. Make sure that all values are correct, then try again.')
                )
        else:
            messages.error(
                request,
                _(
                    "Your organization does not have default roles to review/approve this course-run. "
                    "Please contact your partner manager to create default roles."
                )
            )

        context = self.get_context_data()
        context.update(
            {
                'run_form': run_form,
                'seat_form': seat_form
            }
        )

        return render(request, self.template_name, context, status=400)


class CreateRunFromDashboardView(CreateCourseRunView):
    """ Create Course Run From Dashboard With Type ahead Search For Parent Course."""
    course_form = CourseSearchForm

    def get_context_data(self, **kwargs):
        context = {
            'from_dashboard': True,
            'course_form': self.course_form(),
            'run_form': self.run_form(),
            'seat_form': self.seat_form()
        }
        return context

    def post(self, request, *args, **kwargs):
        course_form = self.course_form(request.POST)
        run_form = self.run_form(request.POST)
        seat_form = self.seat_form(request.POST)
        if course_form.is_valid() and run_form.is_valid() and seat_form.is_valid():
            self.parent_course = course_form.cleaned_data.get('course')
            return super(CreateRunFromDashboardView, self).post(request, *args, **kwargs)

        messages.error(
            request, _('The page could not be updated. Make sure that all values are correct, then try again.')
        )
        context = self.get_context_data()
        context.update(
            {
                'course_form': course_form,
                'run_form': run_form,
                'seat_form': seat_form,
            }
        )
        return render(request, self.template_name, context, status=400)


class CourseRunEditView(mixins.LoginRequiredMixin, mixins.PublisherPermissionMixin, UpdateView):
    """ Course Run Edit View."""
    model = CourseRun
    run_form = CourseRunForm
    seat_form = SeatForm
    template_name = 'publisher/course_run/edit_run_form.html'
    success_url = 'publisher:publisher_course_run_detail'
    form_class = CourseRunForm
    permission = OrganizationExtension.EDIT_COURSE_RUN

    def get_success_url(self):  # pylint: disable=arguments-differ
        return reverse(self.success_url, kwargs={'pk': self.object.id})

    def get_context_data(self):
        user = self.request.user
        return {
            'course_run': self.get_object(),
            'publisher_hide_features_for_pilot': waffle.switch_is_active('publisher_hide_features_for_pilot'),
            'publisher_add_instructor_feature': waffle.switch_is_active('publisher_add_instructor_feature'),
            'is_internal_user': mixins.check_roles_access(user),
            'is_project_coordinator': is_project_coordinator_user(user),
            'organizations': mixins.get_user_organizations(user)
        }

    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        course_run = context.get('course_run')
        course = course_run.course
        course_user_role = course.get_user_role(user=self.request.user)
        if course_user_role == PublisherUserRole.CourseTeam:
            context['organizations_ids'] = list(mixins.get_user_organizations(self.request.user).
                                                values_list('id', flat=True))

        context['course_user_role'] = course_user_role
        context['run_form'] = self.run_form(
            instance=course_run, is_project_coordinator=context.get('is_project_coordinator')
        )
        context['seat_form'] = self.seat_form(instance=course_run.seats.first())

        start_date = course_run.start.strftime("%B %d, %Y") if course_run.start else None
        context['breadcrumbs'] = make_bread_crumbs(
            [
                (reverse('publisher:publisher_courses'), 'Courses'),
                (reverse('publisher:publisher_course_detail', kwargs={'pk': course.id}), course.title),
                (None, '{type}: {start}'.format(
                    type=course_run.get_pacing_type_display(), start=start_date
                ))
            ]
        )

        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        user = request.user

        context = self.get_context_data()
        course_run = context.get('course_run')
        lms_course_id = course_run.lms_course_id

        run_form = self.run_form(
            request.POST, instance=course_run, is_project_coordinator=context.get('is_project_coordinator')
        )
        seat_form = self.seat_form(request.POST, instance=course_run.seats.first())
        if run_form.is_valid() and seat_form.is_valid():
            try:
                with transaction.atomic():

                    course_run = run_form.save(changed_by=user)

                    run_form.save_m2m()

                    # If price-type comes with request then save the seat object.
                    if request.POST.get('type'):
                        seat_form.save(changed_by=user, course_run=course_run)

                    # in case of any updating move the course-run state to draft except draft and published state.
                    immutable_states = [CourseRunStateChoices.Draft, CourseRunStateChoices.Published]

                    course_run_state = course_run.course_run_state
                    if course_run_state.name not in immutable_states:
                        course_run_state.change_state(state=CourseStateChoices.Draft, user=user, site=request.site)

                    if course_run.lms_course_id and lms_course_id != course_run.lms_course_id:
                        emails.send_email_for_studio_instance_created(course_run, site=request.site)

                    # pylint: disable=no-member
                    messages.success(request, _('Course run updated successfully.'))

                    # after editing course owner role will be changed to current user
                    user_role = course_run.course.get_user_role(user=user)
                    if (
                        user_role != course_run_state.owner_role and
                        course_run_state.name != CourseRunStateChoices.Published
                    ):
                        course_run_state.change_owner_role(user_role)

                    if CourseRunStateChoices.Published == course_run_state.name:
                        send_email_for_published_course_run_editing(course_run, request.site)

                    return HttpResponseRedirect(reverse(self.success_url, kwargs={'pk': course_run.id}))
            except Exception as e:  # pylint: disable=broad-except
                # pylint: disable=no-member
                error_message = _('An error occurred while saving your changes. {error}').format(error=str(e))
                messages.error(request, error_message)
                logger.exception('Unable to update course run and seat for course [%s].', course_run.id)

        if not messages.get_messages(request):
            messages.error(
                request, _('The page could not be updated. Make sure that all values are correct, then try again.')
            )
        context.update(
            {
                'run_form': run_form,
                'seat_form': seat_form
            }
        )
        return render(request, self.template_name, context, status=400)


class ToggleEmailNotification(mixins.LoginRequiredMixin, View):
    """ Toggle User Email Notification Settings."""

    def post(self, request):
        is_enabled = json.loads(request.POST.get('is_enabled'))
        user_attribute, __ = UserAttributes.objects.get_or_create(user=request.user)
        user_attribute.enable_email_notification = is_enabled
        user_attribute.save()

        return JsonResponse({'is_enabled': is_enabled})


class CourseListView(mixins.LoginRequiredMixin, ListView):
    paginate_by = COURSES_DEFAULT_PAGE_SIZE

    def get_queryset(self):
        user = self.request.user
        courses = Course.objects.all().prefetch_related(
            'organizations', 'course_state', 'publisher_course_runs', 'course_user_roles'
        )

        if is_publisher_admin(user):
            courses = courses
        elif is_internal_user(user):
            courses = courses.filter(course_user_roles__user=user).distinct()
        else:
            organizations = get_objects_for_user(
                user,
                OrganizationExtension.VIEW_COURSE,
                OrganizationExtension,
                use_groups=True,
                with_superuser=False
            ).values_list('organization')
            courses = courses.filter(organizations__in=organizations)

        courses = self.filter_queryset(courses)
        courses = self.sort_queryset(courses)

        return courses, len(courses)

    def get_context_data(self, **kwargs):
        context = super(CourseListView, self).get_context_data(**kwargs)
        context['publisher_hide_features_for_pilot'] = waffle.switch_is_active('publisher_hide_features_for_pilot')
        site = Site.objects.first()
        context['site_name'] = 'edX' if 'edx' in site.name.lower() else site.name
        context['publisher_courses_url'] = reverse('publisher:publisher_courses')
        context['allowed_page_sizes'] = json.dumps(COURSES_ALLOWED_PAGE_SIZES)
        return context

    def get_paginate_by(self, queryset):
        try:
            page_size = int(self.request.GET.get('pageSize', COURSES_DEFAULT_PAGE_SIZE))
            page_size = page_size if page_size in COURSES_ALLOWED_PAGE_SIZES else COURSES_DEFAULT_PAGE_SIZE
        except ValueError:
            page_size = COURSES_DEFAULT_PAGE_SIZE

        return page_size

    def sort_queryset(self, queryset):
        # commented fields are multi-valued so ordering is not reliable becuase a single
        # record can be returned multiple times. We are not doing ordering for these fields
        ordering_fields = {
            0: 'title',
            # 1: 'organizations__key',
            # 2: 'course_user_roles__user__full_name',
            3: 'course_runs_count',
            4: 'course_state__owner_role_modified',
            5: 'course_state__owner_role_modified',
            6: 'edx_status_column',
            7: 'course_state__owner_role_modified',
        }

        try:
            ordering_field_index = int(self.request.GET.get('sortColumn', 0))
            if ordering_field_index not in ordering_fields.keys():
                raise ValueError
        except ValueError:
            ordering_field_index = 0

        ordering_direction = self.request.GET.get('sortDirection', 'asc')
        ordering_field = ordering_fields.get(ordering_field_index)

        if ordering_field_index == COURSE_RUNS_COUNT_INDEX:
            queryset = queryset.annotate(course_runs_count=Count('publisher_course_runs'))

        # ordering by property *internal user status* of course state
        if ordering_field_index == EDX_STATUS_COLUMN_INDEX:
            course_states = [CourseState.ApprovedByMarketing,
                             CourseState.AwaitingMarketingReview,
                             CourseState.NotAvailable, '']
            if ordering_direction == 'asc':
                queryset = sorted(queryset, key=lambda state: course_states.index(
                    str(state.course_state.internal_user_status if state.course_state.internal_user_status else '')))
            else:
                queryset = sorted(queryset, key=lambda state: course_states.index(
                    str(state.course_state.internal_user_status if state.course_state.internal_user_status else '')),
                    reverse=True)
        else:
            if ordering_direction == 'asc':
                queryset = queryset.order_by(Lower(ordering_field).asc())
            else:
                queryset = queryset.order_by(Lower(ordering_field).desc())

        return queryset

    def filter_queryset(self, queryset):
        filter_text = self.request.GET.get('searchText', '').strip()

        if not filter_text:
            return queryset

        keywords, dates = self.extract_keywords_and_dates(filter_text)

        query_filters = []
        keywords_filter = None
        internal_user_status_query = Q()

        for keyword in keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in str(CourseState.ApprovedByMarketing).lower():
                internal_user_status_query = internal_user_status_query | Q(course_state__marketing_reviewed=True)
            if keyword_lower in str(CourseState.AwaitingMarketingReview).lower():
                internal_user_status_query = internal_user_status_query | (Q(
                    course_state__owner_role=PublisherUserRole.MarketingReviewer) & (
                    Q(course_state__name=CourseStateChoices.Review) | Q(course_state__name=CourseStateChoices.Draft)))
            elif keyword_lower == str(CourseState.NotAvailable).lower():
                internal_user_status_query = internal_user_status_query | (Q(
                    course_state__name=CourseStateChoices.Draft) & Q(
                    course_state__owner_role=PublisherUserRole.CourseTeam))

            keyword_filter = Q(title__icontains=keyword) | Q(organizations__key__icontains=keyword) | Q(
                number__icontains=keyword) | internal_user_status_query
            keywords_filter = (keyword_filter & keywords_filter) if bool(keywords_filter) else keyword_filter

        if keywords_filter:
            query_filters.append(keywords_filter)

        if dates:
            query_filters.append(
                Q(reduce(lambda x, y: x | y, [
                    Q(course_state__owner_role_modified__gte=date['first']) &
                    Q(course_state__owner_role_modified__lt=date['second'])
                    for date in dates
                ]))
            )

        # Filtering is based on keywords and dates. Providing any one of them or both will filter the results.
        # if both are provided then filtering happens according to the below algorithm
        # << select records that contains all the keywords AND the record also contains any of the date >>
        # if user enters multiple dates then we will fetch all records matching any date provided that
        # those records contains all the keywords too. See the below sample records and query results
        #
        # {'title': 'Ops',     'org': 'arbi', 'date': '07/04/17'},
        # {'title': 'Ops'",    'org': 'arbi', 'date': '07/04/17'},
        # {'title': 'Ops',     'org': 'arbi', 'date': '07/10/18'},
        # {'title': 'Ops',     'org': 'arbi', 'date': '07/04/17'},
        # {'title': 'awesome', 'org': 'me',   'date': '07/10/18'},
        #
        # arbi ops                             << select first 4 records
        # arbi 07/04/17 ops                    << select 1st, 2nd and 4th record
        # ops 07/04/17 arbi 07/10/18           << select first 4 records
        # ops 07/04/17 arbi 07/10/18 nope      << no record matches -- all keywords must be present with any of the date
        # 07/10/18                             << select 3rd and last record
        # awesome                              << select last record
        # awesome 07/04/17                     << no record matches

        # distinct is used here to remove duplicate records in case a course has multiple organizations
        # Note: currently this will not happen because each course has one organization only
        return queryset.filter(*query_filters).distinct()

    @staticmethod
    def extract_keywords_and_dates(filter_text):
        """
        Check each keyword in provided list of keywords and parse dates.

        Arguments:
            filter_text (str): input text entered by user like 'intro to python 07/04/17'

        Returns:
            tuple: tuple of two lists, first list contains keywords without dates and
                   second contains list of dicts where each dict has two date objects
        """
        dates = []
        keywords = []
        tokens = filter_text.split()

        for token in tokens:
            try:
                dt = datetime.strptime(token, '%m/%d/%y')
                dates.append({
                    'first': dt,
                    'second': dt + timedelta(days=1),
                })
            except ValueError:
                keywords.append(token)

        return keywords, dates

    def get(self, request, **kwargs):   # pylint: disable=unused-argument
        self.object_list, publisher_total_courses_count = self.get_queryset()
        context = self.get_context_data()
        context['publisher_total_courses_count'] = publisher_total_courses_count
        courses = serializers.CourseSerializer(
            context['object_list'],
            many=True,
            context={
                'user': request.user,
                'publisher_hide_features_for_pilot': context['publisher_hide_features_for_pilot'],
            }
        ).data

        if 'application/json' in request.META.get('HTTP_ACCEPT', ''):
            count = publisher_total_courses_count
            return JsonResponse({
                'draw': int(self.request.GET['draw']),
                'recordsTotal': count,
                'recordsFiltered': count,
                'courses': courses,
            })
        else:
            context['courses'] = JsonResponse(courses, safe=False).content
            return self.render_to_response(context)


class CourseRevisionView(mixins.LoginRequiredMixin, DetailView):
    """Course revisions view """
    model = Course
    template_name = 'publisher/course_revision_history.html'

    def get_context_data(self, **kwargs):
        context = super(CourseRevisionView, self).get_context_data(**kwargs)

        try:
            context['history_object'] = self.object.history.get(history_id=self.kwargs.get('revision_id'))
        except ObjectDoesNotExist:
            raise Http404

        return context


def get_course_role_widgets_data(user, course, state_object, change_state_url, parent_course=False):
    """ Create role widgets list for course user roles. """
    role_widgets = []
    course_roles = course.course_user_roles.exclude(role=PublisherUserRole.MarketingReviewer)
    roles = [PublisherUserRole.CourseTeam, PublisherUserRole.ProjectCoordinator]
    if parent_course:
        roles = [PublisherUserRole.CourseTeam, PublisherUserRole.MarketingReviewer]
        course_roles = course.course_user_roles.filter(role__in=roles)

    for course_role in course_roles.order_by('role'):
        role_widget = {
            'course_role': course_role,
            'heading': ROLE_WIDGET_HEADINGS.get(course_role.role),
            'change_state_url': reverse(change_state_url, kwargs={'pk': state_object.id})
        }

        if is_internal_user(user):
            role_widget['user_list'] = get_internal_users()
            if course_role.role != PublisherUserRole.CourseTeam:
                role_widget['can_change_role_assignment'] = True

        if course_role.role == PublisherUserRole.CourseTeam:
            role_widget['user_list'] = course.organization_extension.group.user_set.all()
            if user.groups.filter(name=course.organization_extension.group).exists():
                role_widget['can_change_role_assignment'] = True

        if state_object.owner_role == course_role.role:
            if state_object.owner_role_modified:
                role_widget['ownership'] = timezone.now() - state_object.owner_role_modified

            if user == course_role.user:
                role_widget['state_button'] = STATE_BUTTONS.get(state_object.name)

                if state_object.name == CourseStateChoices.Draft and not state_object.can_send_for_review():
                    role_widget['button_disabled'] = True

        if course_role.role in roles:
            reviewed_states = [CourseStateChoices.Approved, CourseRunStateChoices.Published]
            if state_object.name in reviewed_states and course_role.role == state_object.approved_by_role:
                history_record = state_object.history.filter(
                    name=CourseStateChoices.Approved
                ).order_by('-modified').first()
                if history_record:
                    role_widget['reviewed'] = history_record.modified

            elif ((state_object.name != CourseStateChoices.Draft and course_role.role != state_object.owner_role) or
                  state_object.name == CourseRunStateChoices.Approved):

                history_record = state_object.history.filter(
                    name=CourseStateChoices.Review
                ).order_by('-modified').first()
                if history_record:
                    if hasattr(state_object, 'marketing_reviewed') and state_object.marketing_reviewed:
                        role_widget['reviewed'] = history_record.modified
                    else:
                        role_widget['sent_for_review'] = history_record.modified

        role_widgets.append(role_widget)

    return role_widgets


class AdminImportCourse(mixins.LoginRequiredMixin, TemplateView):
    """Admin page to import course from course-metadata to publisher. """
    # page is accessible to the admin users and also if the waffle switch is enable.

    model = Course
    template_name = 'publisher/admin/import_course.html'

    def get_context_data(self, **kwargs):
        context = super(AdminImportCourse, self).get_context_data(**kwargs)
        context['form'] = AdminImportCourseForm()

        return context

    def get(self, request, *args, **kwargs):
        """Get method for import page."""
        if self.request.user.is_superuser and waffle.switch_is_active('publisher_enable_course_import'):
            return super(AdminImportCourse, self).get(request, args, **kwargs)
        else:
            raise Http404

    def post(self, request, *args, **kwargs):
        """Post method for import page."""

        #  inline import to avoid any circular issues.
        from course_discovery.apps.course_metadata.models import Course as CourseMetaData

        if not (self.request.user.is_superuser and waffle.switch_is_active('publisher_enable_course_import')):
            raise Http404

        form = AdminImportCourseForm(request.POST)
        if form.is_valid():

            start_id = self.request.POST.get('start_id')

            try:
                course = CourseMetaData.objects.select_related('canonical_course_run', 'level_type', 'video').get(
                    id=start_id
                )
                process_course(course)

                # check publisher db that course is available now.
                publisher_course = Course.objects.filter(course_metadata_pk=start_id)

                if publisher_course.exists():
                    publisher_course = publisher_course.first()
                    organization = publisher_course.organizations.first()

                    # if org has default organization then add its roles.
                    if (
                        hasattr(organization, 'organization_extension') and
                        organization.organization_user_roles.filter(
                            role__in=DEFAULT_ROLES).count() == len(DEFAULT_ROLES)
                    ):
                        mixins.check_and_create_course_user_roles(publisher_course)

                    messages.success(request, 'Course Imported')
                else:
                    messages.error(request, 'Some error occurred. Please check authoring organizations of course.')

            except Exception as ex:  # pylint: disable=broad-except
                messages.error(request, str(ex))

        return super(AdminImportCourse, self).get(request, args, **kwargs)


class EmailPreviewView(mixins.LoginRequiredMixin, TemplateView):    # pragma: no cover
    template_name = 'publisher/email_preview.html'

    def get_email_content(self):
        # NOTE: It is up to you, the developer, to place content here.
        # The simplest approach is to simply copy the code from publisher.emails
        # and paste it here.
        # txt_template = 'publisher/email/course_run/preview_available.txt'
        # html_template = 'publisher/email/course_run/preview_available.html'
        # course_run = CourseRun.objects.first()
        # site = Site.objects.first()
        # course_key = CourseKey.from_string(course_run.lms_course_id)
        # context = {
        #     'sender_role': PublisherUserRole.Publisher,
        #     'recipient_name': 'DEMO USER',
        #     'course_run': course_run,
        #     'course_run_key': course_key,
        #     'course_run_publisher_url': 'https://{host}{path}'.format(
        #         host=site.domain.strip('/'), path=course_run.get_absolute_url()),
        #     'contact_us_email': 'demo@example.com',
        #     'platform_name': settings.PLATFORM_NAME,
        # }
        # template = get_template(txt_template)
        # plain_content = template.render(context)
        # template = get_template(html_template)
        # html_content = template.render(context)
        #
        # return plain_content, html_content
        raise NotImplementedError

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        text_content, html_content = self.get_email_content()

        context.update({
            'html_content': html_content,
            'text_content': text_content,
        })
        return context
