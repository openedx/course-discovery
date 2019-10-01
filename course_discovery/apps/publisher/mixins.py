from functools import wraps
from urllib import parse

from dal import autocomplete
from django.contrib.auth.decorators import login_required
from django.db.models.functions import Lower
from django.http import HttpResponseForbidden, HttpResponsePermanentRedirect, HttpResponseRedirect
from django.utils.decorators import method_decorator

from course_discovery.apps.core.models import User
from course_discovery.apps.course_metadata.models import Organization
from course_discovery.apps.publisher.choices import PublisherUserRole
from course_discovery.apps.publisher.models import Course, CourseUserRole, Seat
from course_discovery.apps.publisher.utils import is_internal_user, is_publisher_admin, is_publisher_user


def enforce_site_host(func):
    """
    Decorator to redirect any incoming request where the hostname does not match the site's domain.
    In such cases, we redirect the user to the same URL using the domain from the site.

    This is useful when migrating from one hostname to another.
    """
    def inner(self, request, *args, **kwargs):
        if request.get_host() != request.site.domain:
            parts = parse.urlparse(request.build_absolute_uri())
            url = parse.urlunparse(parts._replace(netloc=request.site.domain))
            return HttpResponsePermanentRedirect(url)
        return func(self, request, *args, **kwargs)
    return inner


class PublisherPermissionMixin:
    """
    This class will check the logged in user permission for a given course object.
    """

    permission = None

    def get_course(self):
        publisher_object = self.get_object()
        if isinstance(publisher_object, Course):
            return publisher_object
        if isinstance(publisher_object, Seat):
            return publisher_object.course_run.course
        if hasattr(publisher_object, 'course'):
            return publisher_object.course

        return None

    def has_user_access(self, user):
        """ check has the access on course.
        If user is publisher admin or internal user return True otherwise
        check user has the organization permission on the given course.

        Arguments:
            user (User): User object

        Returns:
            Boolean
        """
        course = self.get_course()
        return (
            check_roles_access(user) or
            check_course_organization_permission(user, course, self.permission)
        )

    def permission_failed(self):
        return HttpResponseForbidden()

    @enforce_site_host
    def dispatch(self, request, *args, **kwargs):
        if not self.has_user_access(request.user):
            return self.permission_failed()

        return super(PublisherPermissionMixin, self).dispatch(request, *args, **kwargs)


class LoginRequiredMixin:

    @enforce_site_host
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        return super(LoginRequiredMixin, self).dispatch(request, *args, **kwargs)


class FormValidMixin:
    change_state = False

    def form_valid(self, form):
        user = self.request.user
        publisher_object = form.save(commit=False)
        publisher_object.changed_by = user
        publisher_object.save()
        form.save_m2m()

        self.object = publisher_object

        return HttpResponseRedirect(self.get_success_url())


def check_roles_access(user):
    """ Return True if user is part of a role that gives implicit access. """
    return is_publisher_admin(user) or is_internal_user(user)


def check_course_organization_permission(user, course, permission):
    """ Return True if user has view permission on organization. """
    if not hasattr(course, 'organizations'):
        return False

    return any(
        [
            user.has_perm(permission, org.organization_extension)
            for org in course.organizations.all()
        ]
    )


def publisher_user_required(func):
    """
    View decorator that requires that the user is part any publisher group
    permissions.
    """
    @wraps(func)
    def wrapped(request, *args, **kwargs):
        if is_publisher_user(request.user):
            return func(request, *args, **kwargs)
        else:
            return HttpResponseForbidden(u"Must be Publisher user to perform this action.")

    return wrapped


class PublisherUserRequiredMixin:
    """
    Mixin to view the user is part of any publisher app group.
    """
    @enforce_site_host
    @method_decorator(publisher_user_required)
    def dispatch(self, request, *args, **kwargs):
        return super(PublisherUserRequiredMixin, self).dispatch(request, *args, **kwargs)


class LanguageModelSelect2Multiple(autocomplete.ModelSelect2Multiple):
    """
    QuerySet support for LanguageTag choices.

    django.autocomplete queryset expects id field to filter choices but LanguageTag
    does not have id field in it. It has code as primary key instead of id.
    """

    def filter_choices_to_render(self, selected_choices):
        self.choices.queryset = self.choices.queryset.filter(
            code__in=[c for c in selected_choices if c]
        )


def get_user_organizations(user):
    """
    Get organizations for user.

    Args:
        user (Object): User object
    Returns:
        Organization (QuerySet): returns Organization objects queryset
    """
    organizations = Organization.objects.filter(
        organization_extension__organization_id__isnull=False
    ).order_by(Lower('key'))

    if not check_roles_access(user):
        # If not internal user return only those organizations which belongs to user.
        organizations = organizations.filter(
            organization_extension__group__in=user.groups.all()
        ).order_by(Lower('key'))

    return organizations


def add_course_role(course, organization_extension, role):
    default_role = organization_extension.organization.organization_user_roles.get(role=role)
    CourseUserRole.add_course_roles(course=course, role=default_role.role, user=default_role.user)


def check_and_create_course_user_roles(course):
    organization_extension = course.organization_extension

    if not course.course_team_admin:
        course_team_users = User.objects.filter(groups__name=organization_extension.group.name)
        CourseUserRole.add_course_roles(
            course=course, role=PublisherUserRole.CourseTeam, user=course_team_users.first()
        )

    if not course.project_coordinator:
        add_course_role(course, organization_extension, PublisherUserRole.ProjectCoordinator)

    if not course.publisher:
        add_course_role(course, organization_extension, PublisherUserRole.Publisher)

    if not course.marketing_reviewer:
        add_course_role(course, organization_extension, PublisherUserRole.MarketingReviewer)
