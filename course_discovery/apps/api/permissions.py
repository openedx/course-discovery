from rest_framework.permissions import SAFE_METHODS, BasePermission

from course_discovery.apps.course_metadata.models import CourseEditor


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
