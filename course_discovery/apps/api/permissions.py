from rest_framework.permissions import SAFE_METHODS, BasePermission, DjangoModelPermissions

from course_discovery.apps.course_metadata.models import CourseEditor
from course_discovery.apps.course_metadata.utils import parse_course_key_fragment


class ReadOnlyByPublisherUser(BasePermission):
    """
    Custom Permission class to check user is a publisher user.
    """
    def has_permission(self, request, view):
        if request.method == 'GET':
            return request.user.groups.exists()
        return True


class IsCourseEditorOrReadOnly(BasePermission):
    """
    Custom Permission class to check user is a course editor for the course, if they are trying to write.
    """
    def has_permission(self, request, view):
        if request.method == 'POST':
            org = request.data.get('org')
            return org and CourseEditor.can_create_course(request.user, org)
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
                return False
            org, _ = parse_course_key_fragment(course)
            return org and CourseEditor.can_create_course(request.user, org)
        else:
            return True  # other write access attempts will be caught by object permissions below

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        else:
            return CourseEditor.is_course_editable(request.user, obj.course)
