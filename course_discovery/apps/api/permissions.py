from django.conf import settings
from rest_framework.permissions import SAFE_METHODS, BasePermission, DjangoModelPermissions

from course_discovery.apps.course_metadata.models import CourseEditor
from course_discovery.apps.course_metadata.utils import parse_course_key_fragment

USERNAME_REPLACEMENT_GROUP = "username_replacement_admin"


class ReadOnlyByPublisherUser(BasePermission):
    """
    Custom Permission class to check user is a publisher user or a staff user.
    """
    def has_permission(self, request, view):
        if request.method == 'GET':
            return request.user.is_staff or request.user.groups.exists()
        return True


class IsInOrgOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        else:
            org = request.data.get('org')
            if not org:
                # Fail happily because OPTIONS goes down this path too with a fake POST.
                # If this is a real POST, we'll complain about the missing org in the view.
                return True
            return CourseEditor.can_create_course(request.user, org)


class IsCourseEditorOrReadOnly(BasePermission):
    """
    Custom Permission class to check user is a course editor for the course, if they are trying to write.
    """
    def has_permission(self, request, view):
        if request.method == 'POST':
            org = request.data.get('org')
            if not org:
                # Fail happily because OPTIONS goes down this path too with a fake POST.
                # If this is a real POST, we'll complain about the missing org in the view.
                return True
            return CourseEditor.can_create_course(request.user, org)
        else:
            return True  # other write access attempts will be caught by object permissions below

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        else:
            return CourseEditor.is_course_editable(request.user, obj)


class IsCourseRunEditorOrDjangoOrReadOnly(BasePermission):
    """
    Custom Permission class to check user is a course editor for the course or has django model access
    """
    def __init__(self):
        self.django_perms = DjangoModelPermissions()

    def has_permission(self, request, view):
        if self.django_perms.has_permission(request, view):
            return True
        elif request.user.is_staff:
            return True
        elif request.method == 'POST':
            course = request.data.get('course')
            if not course:
                # Fail happily because OPTIONS goes down this path too with a fake POST.
                # If this is a real POST, we'll complain about the missing course in the view.
                return True
            org, _ = parse_course_key_fragment(course)
            return org and CourseEditor.can_create_course(request.user, org)
        else:
            return True  # other write access attempts will be caught by object permissions below

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        else:
            return CourseEditor.is_course_editable(request.user, obj.course)


class CanReplaceUsername(BasePermission):
    """
    Grants access to the Username Replacement API for the service user.
    """
    def has_permission(self, request, view):
        return request.user.username == settings.USERNAME_REPLACEMENT_WORKER


class CanAppointCourseEditor(BasePermission):

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        else:
            course = request.data.get('course')
            if not course:
                # Fail happily because OPTIONS goes down this path too with a fake POST.
                # If this is a real POST, we'll complain about the missing course in the view.
                return True

            # We could do a lookup on the course from the request above, but the logic already exists in the view so we
            # use that to avoid writing it twice
            return CourseEditor.is_course_editable(request.user, view.course)
