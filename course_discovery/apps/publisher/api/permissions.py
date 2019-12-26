from rest_framework.permissions import BasePermission

from course_discovery.apps.publisher.utils import is_publisher_user


class PublisherUserPermission(BasePermission):
    """ Permission class to check user is a publisher user. """

    def has_object_permission(self, request, view, obj):
        return request.user.is_staff or is_publisher_user(request.user)

    def has_permission(self, request, view):
        return request.user.is_staff or is_publisher_user(request.user)
