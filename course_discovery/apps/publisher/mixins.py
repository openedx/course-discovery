from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.utils.decorators import method_decorator

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


class LoginRequiredMixin(object):

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        return super(LoginRequiredMixin, self).dispatch(request, *args, **kwargs)


class FormValidMixin(object):
    change_state = False
    assign_user_groups = False

    def form_valid(self, form):
        user = self.request.user
        publisher_object = form.save(commit=False)
        publisher_object.changed_by = user
        publisher_object.save()

        if self.assign_user_groups:
            publisher_object.assign_user_groups(user)

        if self.change_state:
            publisher_object.change_state(user=user)

        self.object = publisher_object

        return HttpResponseRedirect(self.get_success_url())


def check_view_permission(user, course):
    return user.is_staff or user.has_perm(Course.VIEW_PERMISSION, course)


def get_group_users_with_permission(user, publisher_object):
    """ Helper method to check user in a group has permission on publisher object."""
    users_list = []
    user_groups = user.groups.all()
    if not user_groups:
        return users_list

    for group in user_groups:
        for user in group.user_set.all():
            if check_view_permission(user, publisher_object):
                users_list.append(user)

    return users_list
