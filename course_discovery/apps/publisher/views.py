"""
Course publisher views.
"""
import json
import logging
from datetime import datetime, timedelta
import waffle

from django.contrib import messages
from django.core.urlresolvers import reverse
from django.db import transaction
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.utils.translation import ugettext_lazy as _
from django.views.generic import View, CreateView, UpdateView, DetailView, ListView
from django_fsm import TransitionNotAllowed
from guardian.shortcuts import get_objects_for_user

from course_discovery.apps.core.models import User
from course_discovery.apps.publisher.choices import PublisherUserRole
from course_discovery.apps.publisher.forms import (
    CourseForm, CourseRunForm, SeatForm, CustomCourseForm, CustomCourseRunForm,
    CustomSeatForm, UpdateCourseForm
)
from course_discovery.apps.publisher import mixins
from course_discovery.apps.publisher.models import (
    Course, CourseRun, Seat, State, UserAttributes,
    OrganizationExtension, CourseUserRole)
from course_discovery.apps.publisher.utils import (
    is_internal_user, get_internal_users, is_publisher_admin,
    is_partner_coordinator_user
)
from course_discovery.apps.publisher.wrappers import CourseRunWrapper

logger = logging.getLogger(__name__)


SEATS_HIDDEN_FIELDS = ['price', 'currency', 'upgrade_deadline', 'credit_provider', 'credit_hours']

ROLE_WIDGET_HEADINGS = {
    PublisherUserRole.PartnerCoordinator: _('PARTNER COORDINATOR'),
    PublisherUserRole.MarketingReviewer: _('MARKETING'),
    PublisherUserRole.Publisher: _('PUBLISHER'),
    PublisherUserRole.CourseTeam: _('Course Team')
}


class Dashboard(mixins.LoginRequiredMixin, ListView):
    """ Create Course View."""
    template_name = 'publisher/dashboard.html'
    default_published_days = 30

    def get_queryset(self):
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
        context = super(Dashboard, self).get_context_data(**kwargs)
        course_runs = context.get('object_list')

        published_course_runs = course_runs.filter(
            state__name=State.PUBLISHED,
            state__modified__gt=datetime.today() - timedelta(days=self.default_published_days)
        ).select_related('state').order_by('-state__modified')

        unpublished_course_runs = course_runs.exclude(state__name=State.PUBLISHED)

        # Studio requests needs to check depending upon the user role with course
        # Also user should be part of partner coordinator group.
        if is_publisher_admin(self.request.user):
            studio_request_courses = unpublished_course_runs.filter(lms_course_id__isnull=True)
        elif is_partner_coordinator_user(self.request.user):
            studio_request_courses = unpublished_course_runs.filter(lms_course_id__isnull=True).filter(
                course__course_user_roles__role=PublisherUserRole.PartnerCoordinator
            )
        else:
            studio_request_courses = []

        context['studio_request_courses'] = [CourseRunWrapper(course_run) for course_run in studio_request_courses]
        context['unpublished_course_runs'] = [CourseRunWrapper(course_run) for course_run in unpublished_course_runs]
        context['published_course_runs'] = [CourseRunWrapper(course_run) for course_run in published_course_runs]
        context['default_published_days'] = self.default_published_days

        in_progress_course_runs = course_runs.filter(
            state__name=State.NEEDS_FINAL_APPROVAL
        ).select_related('state').order_by('-state__modified')

        preview_course_runs = in_progress_course_runs.filter(
            preview_url__isnull=False
        ).order_by('-state__modified')

        context['in_progress_course_runs'] = [CourseRunWrapper(course_run) for course_run in in_progress_course_runs]
        context['preview_course_runs'] = [CourseRunWrapper(course_run) for course_run in preview_course_runs]

        return context


class CourseRunDetailView(mixins.LoginRequiredMixin, mixins.PublisherPermissionMixin, DetailView):
    """ Course Run Detail View."""
    model = CourseRun
    template_name = 'publisher/course_run_detail.html'
    permission = OrganizationExtension.VIEW_COURSE_RUN

    def get_role_widgets_data(self, course_roles):
        """ Create role widgets list for course user roles. """
        role_widgets = []
        for course_role in course_roles:
            role_widgets.append(
                {
                    'user_course_role': course_role,
                    'heading': ROLE_WIDGET_HEADINGS.get(course_role.role)
                }
            )

        return role_widgets

    def get_context_data(self, **kwargs):
        context = super(CourseRunDetailView, self).get_context_data(**kwargs)

        user = self.request.user
        course_run = CourseRunWrapper(self.get_object())
        context['object'] = course_run
        context['comment_object'] = course_run.course
        context['can_edit'] = mixins.check_course_organization_permission(
            self.request.user, course_run.course, OrganizationExtension.EDIT_COURSE_RUN
        )

        # Show role assignment widgets if user is an internal user.
        if is_internal_user(user):
            course_roles = course_run.course.course_user_roles.exclude(role=PublisherUserRole.CourseTeam)
            context['role_widgets'] = self.get_role_widgets_data(course_roles)
            context['user_list'] = get_internal_users()

        context['breadcrumbs'] = [
            {
                'url': reverse('publisher:publisher_courses'), 'slug': 'Courses'
            },
            {
                'url': reverse('publisher:publisher_course_detail', kwargs={'pk': course_run.course.id}),
                'slug': course_run.course.title
            },
            {
                'url': None,
                'slug': '{type}: {start}'.format(
                    type=course_run.get_pacing_type_display(), start=course_run.start.strftime("%B %d, %Y")
                )
            }
        ]

        context['can_view_all_tabs'] = mixins.check_roles_access(self.request.user)
        context['publisher_hide_features_for_pilot'] = waffle.switch_is_active('publisher_hide_features_for_pilot')

        return context


# pylint: disable=attribute-defined-outside-init
class CreateCourseView(mixins.LoginRequiredMixin, mixins.PublisherUserRequiredMixin, CreateView):
    """ Create Course View."""
    model = Course
    course_form = CustomCourseForm
    run_form = CustomCourseRunForm
    seat_form = CustomSeatForm
    template_name = 'publisher/add_course_form.html'
    success_url = 'publisher:publisher_course_run_detail'

    def get_success_url(self, course_id):  # pylint: disable=arguments-differ
        return reverse(self.success_url, kwargs={'pk': course_id})

    def get_context_data(self):
        return {
            'course_form': self.course_form,
            'run_form': self.run_form,
            'seat_form': self.seat_form,
            'publisher_hide_features_for_pilot': waffle.switch_is_active('publisher_hide_features_for_pilot')
        }

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context_data())

    def post(self, request, *args, **kwargs):
        ctx = self.get_context_data()

        # pass selected organization to CustomCourseForm to populate related
        # choices into institution admin field
        organization = self.request.POST.get('organization')
        course_form = self.course_form(request.POST, request.FILES, organization=organization)
        run_form = self.run_form(request.POST)
        seat_form = self.seat_form(request.POST)
        if course_form.is_valid() and run_form.is_valid() and seat_form.is_valid():
            try:
                with transaction.atomic():
                    seat = None
                    if request.POST.get('type'):
                        seat = seat_form.save(commit=False)

                    run_course = run_form.save(commit=False)
                    course = course_form.save(commit=False)
                    course.changed_by = self.request.user
                    course.save()
                    # commit false does not save m2m object. Keyword field is m2m.
                    course_form.save_m2m()

                    run_course.course = course
                    run_course.changed_by = self.request.user
                    run_course.save()

                    # commit false does not save m2m object.
                    run_form.save_m2m()

                    if seat:
                        seat.course_run = run_course
                        seat.changed_by = self.request.user
                        seat.save()

                    organization_extension = get_object_or_404(
                        OrganizationExtension, organization=course_form.data['organization']
                    )
                    course.organizations.add(organization_extension.organization)

                    # add default organization roles into course-user-roles
                    course.assign_organization_role(organization_extension.organization)

                    # add team admin as CourseTeam role again course
                    CourseUserRole.add_course_roles(course=course, role=PublisherUserRole.CourseTeam,
                                                    user=User.objects.get(id=course_form.data['team_admin']))

                    # pylint: disable=no-member
                    messages.success(request, _(
                        'EdX will create a Studio instance for this course. You will receive a notification message at '
                        '{email} when the Studio instance has been created.').format(email=request.user.email))

                    return HttpResponseRedirect(self.get_success_url(run_course.id))
            except Exception as e:  # pylint: disable=broad-except
                # pylint: disable=no-member
                error_message = _('An error occurred while saving your changes. {error}').format(error=str(e))
                messages.error(request, error_message)

        if not messages.get_messages(request):
            messages.error(request, _('Please fill all required fields.'))

        if course_form.errors.get('image'):
            messages.error(request, course_form.errors.get('image'))

        ctx.update(
            {
                'course_form': course_form,
                'run_form': run_form,
                'seat_form': seat_form
            }
        )
        return render(request, self.template_name, ctx, status=400)


class CourseEditView(mixins.PublisherPermissionMixin, mixins.FormValidMixin, UpdateView):
    """ Course Edit View."""
    model = Course
    form_class = CourseForm
    permission = OrganizationExtension.EDIT_COURSE
    template_name = 'publisher/course_form.html'
    success_url = 'publisher:publisher_course_detail'

    def get_success_url(self):
        return reverse(self.success_url, kwargs={'pk': self.object.id})

    def get_context_data(self, **kwargs):
        context = super(CourseEditView, self).get_context_data(**kwargs)
        context['comment_object'] = self.object
        return context


class CourseDetailView(mixins.LoginRequiredMixin, mixins.PublisherPermissionMixin, DetailView):
    """ Course Detail View."""
    model = Course
    template_name = 'publisher/view_course_form.html'
    permission = OrganizationExtension.VIEW_COURSE

    def get_context_data(self, **kwargs):
        context = super(CourseDetailView, self).get_context_data(**kwargs)

        context['can_edit'] = mixins.check_course_organization_permission(
            self.request.user, self.object, OrganizationExtension.EDIT_COURSE
        )

        context['breadcrumbs'] = [
            {
                'url': reverse('publisher:publisher_courses'), 'slug': 'Courses'
            },
            {
                'url': None,
                'slug': self.object.title
            }
        ]

        return context


class CreateCourseRunView(mixins.LoginRequiredMixin, CreateView):
    """ Create Course Run View."""
    model = CourseRun
    course_form = UpdateCourseForm
    run_form = CustomCourseRunForm
    seat_form = CustomSeatForm
    template_name = 'publisher/add_courserun_form.html'
    success_url = 'publisher:publisher_course_run_detail'
    parent_course = None
    fields = ()

    def get_parent_course(self):
        if not self.parent_course:
            self.parent_course = get_object_or_404(Course, pk=self.kwargs.get('parent_course_id'))

        return self.parent_course

    def get_context_data(self, **kwargs):
        parent_course = self.get_parent_course()
        course_form = self.course_form(instance=parent_course)
        user_role = CourseUserRole.objects.get(course=parent_course, role=PublisherUserRole.CourseTeam)
        context = {
            'parent_course': parent_course,
            'course_form': course_form,
            'run_form': self.run_form,
            'seat_form': self.seat_form,
            'is_team_admin_hidden': user_role.user and 'team_admin' not in course_form.errors
        }
        return context

    def post(self, request, *args, **kwargs):
        user = request.user
        parent_course = self.get_parent_course()
        course_form = self.course_form(request.POST, instance=self.get_parent_course())
        run_form = self.run_form(request.POST)
        seat_form = self.seat_form(request.POST)
        if course_form.is_valid() and run_form.is_valid() and seat_form.is_valid():
            try:
                with transaction.atomic():
                    course = course_form.save(changed_by=user)
                    course_run = run_form.save(course=course, changed_by=user)
                    seat_form.save(course_run=course_run, changed_by=user)

                    # pylint: disable=no-member
                    success_msg = _('Course run created successfully for course "{course_title}".').format(
                        course_title=course.title
                    )
                    messages.success(request, success_msg)
                    return HttpResponseRedirect(reverse(self.success_url, kwargs={'pk': course_run.id}))
            except Exception as error:  # pylint: disable=broad-except
                # pylint: disable=no-member
                error_msg = _('There was an error saving course run, {error}').format(error=error)
                messages.error(request, error_msg)
                logger.exception('Unable to create course run and seat for course [%s].', parent_course.id)
        else:
            messages.error(request, _('Please fill all required fields.'))

        context = self.get_context_data()
        user_role = CourseUserRole.objects.get(course=parent_course, role=PublisherUserRole.CourseTeam)
        context.update(
            {
                'course_form': course_form,
                'run_form': run_form,
                'seat_form': seat_form,
                'is_team_admin_hidden': user_role.user and 'team_admin' not in course_form.errors
            }
        )

        return render(request, self.template_name, context, status=400)


class UpdateCourseRunView(mixins.LoginRequiredMixin, mixins.PublisherPermissionMixin, mixins.FormValidMixin, UpdateView):  # pylint: disable=line-too-long
    """ Update Course Run View."""
    model = CourseRun
    form_class = CourseRunForm
    permission = OrganizationExtension.VIEW_COURSE
    template_name = 'publisher/course_run_form.html'
    success_url = 'publisher:publisher_course_runs_edit'
    change_state = True

    def get_context_data(self, **kwargs):
        context = super(UpdateCourseRunView, self).get_context_data(**kwargs)
        if not self.object:
            self.object = self.get_object()
        context['workflow_state'] = self.object.current_state
        context['comment_object'] = self.object
        return context

    def get_success_url(self):
        return reverse(self.success_url, kwargs={'pk': self.object.id})


class CreateSeatView(mixins.LoginRequiredMixin, mixins.FormValidMixin, CreateView):
    """ Create Seat View."""
    model = Seat
    form_class = SeatForm
    template_name = 'publisher/seat_form.html'
    success_url = 'publisher:publisher_seats_edit'

    def get_context_data(self, **kwargs):
        context = super(CreateSeatView, self).get_context_data(**kwargs)
        context['hidden_fields'] = SEATS_HIDDEN_FIELDS
        return context

    def get_success_url(self):
        return reverse(self.success_url, kwargs={'pk': self.object.id})


class UpdateSeatView(mixins.LoginRequiredMixin, mixins.PublisherPermissionMixin, mixins.FormValidMixin, UpdateView):
    """ Update Seat View."""
    model = Seat
    form_class = SeatForm
    permission = OrganizationExtension.EDIT_COURSE_RUN
    template_name = 'publisher/seat_form.html'
    success_url = 'publisher:publisher_seats_edit'

    def get_context_data(self, **kwargs):
        context = super(UpdateSeatView, self).get_context_data(**kwargs)
        context['hidden_fields'] = SEATS_HIDDEN_FIELDS
        context['comment_object'] = self.object
        return context

    def get_success_url(self):
        return reverse(self.success_url, kwargs={'pk': self.object.id})


class ChangeStateView(mixins.LoginRequiredMixin, mixins.PublisherPermissionMixin, UpdateView):
    """ Change Workflow State View"""

    model = CourseRun
    permission = OrganizationExtension.EDIT_COURSE_RUN

    def post(self, request, **kwargs):
        state = request.POST.get('state')
        course_run = self.get_object()
        try:
            course_run.change_state(target=state, user=self.request.user)
            # pylint: disable=no-member
            messages.success(
                request, _('Content moved to `{state}` successfully.').format(state=course_run.current_state)
            )
            return HttpResponseRedirect(reverse('publisher:publisher_course_run_detail', kwargs={'pk': course_run.id}))
        except (CourseRun.DoesNotExist, TransitionNotAllowed):
            messages.error(request, _('There was an error in changing state.'))
            return HttpResponseRedirect(reverse('publisher:publisher_course_run_detail', kwargs={'pk': course_run.id}))


class ToggleEmailNotification(mixins.LoginRequiredMixin, View):
    """ Toggle User Email Notification Settings."""

    def post(self, request):
        is_enabled = json.loads(request.POST.get('is_enabled'))
        user_attribute, __ = UserAttributes.objects.get_or_create(user=request.user)
        user_attribute.enable_email_notification = is_enabled
        user_attribute.save()

        return JsonResponse({'is_enabled': is_enabled})


class CourseListView(mixins.LoginRequiredMixin, ListView):
    """ Course List View."""
    template_name = 'publisher/courses.html'

    def get_queryset(self):
        user = self.request.user
        if is_publisher_admin(user):
            courses = Course.objects.all()
        elif is_internal_user(user):
            courses = Course.objects.filter(course_user_roles__user=user).distinct()
        else:
            organizations = get_objects_for_user(
                user,
                OrganizationExtension.VIEW_COURSE,
                OrganizationExtension,
                use_groups=True,
                with_superuser=False
            ).values_list('organization')
            courses = Course.objects.filter(organizations__in=organizations)

        return courses
