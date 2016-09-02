from django.http import HttpResponseForbidden

from course_discovery.apps.publisher.models import Course, CourseRun, Seat


class ViewPermissionMixin(object):
    permission_failure_url = ''

    def get_course(self):
        course_object = self.get_object()
        if isinstance(course_object, CourseRun):
            return course_object.course
        if isinstance(course_object, Seat):
            return course_object.course_run.course

        return course_object

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
