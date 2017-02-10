from rest_framework.permissions import BasePermission

from course_discovery.apps.publisher.mixins import check_course_organization_permission, check_roles_access
from course_discovery.apps.publisher.models import OrganizationExtension
from course_discovery.apps.publisher.utils import is_internal_user, is_publisher_user


class CanViewAssociatedCourse(BasePermission):
    """ Permission class to check user can view a publisher course or also if
    user has view permission on organization.
    """

    def has_object_permission(self, request, view, obj):
        user = request.user
        return (
            check_roles_access(user) or
            check_course_organization_permission(user, obj.course, OrganizationExtension.VIEW_COURSE)
        )


class InternalUserPermission(BasePermission):
    """ Permission class to check user is an internal user. """

    def has_object_permission(self, request, view, obj):
        return is_internal_user(request.user)


class PublisherUserPermission(BasePermission):
    """ Permission class to check user is a publisher user. """

    def has_object_permission(self, request, view, obj):
        return is_publisher_user(request.user)
