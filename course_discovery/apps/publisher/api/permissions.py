from rest_framework.permissions import BasePermission

from course_discovery.apps.publisher.mixins import check_view_permission
from course_discovery.apps.publisher.utils import is_internal_user


class CanViewAssociatedCourse(BasePermission):
    """ Permission class to check user can view a publisher course. """

    def has_object_permission(self, request, view, obj):
        return check_view_permission(request.user, obj.course)


class InternalUserPermission(BasePermission):
    """ Permission class to check user is an internal user. """

    def has_object_permission(self, request, view, obj):
        return is_internal_user(request.user)
