from django.http import HttpResponseForbidden

from course_discovery.apps.publisher.models import Course, Seat


class ViewPermissionMixin(object):

    def get_course(self):
        publisher_object = self.get_object()
        if isinstance(publisher_object, Course):
            return publisher_object
        if isinstance(publisher_object, Seat):
            return publisher_object.course_run.course
        if hasattr(publisher_object, 'course'):
            return publisher_object.course

        return None

    def check_user(self, user):
        course = self.get_course()
        return check_view_permission(user, course)

    def permission_failed(self):
        return HttpResponseForbidden()

    def dispatch(self, request, *args, **kwargs):
        if not self.check_user(request.user):
            return self.permission_failed()

        return super(ViewPermissionMixin, self).dispatch(request, *args, **kwargs)


def check_view_permission(user, course):
    return user.is_staff or user.has_perm(Course.VIEW_PERMISSION, course)
