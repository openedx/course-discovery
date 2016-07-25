"""
Course publisher views.
"""
from django.http import HttpResponseRedirect
from django.views.generic import edit
from course_discovery.apps.publisher.forms import CourseForm, CourseRunForm, SeatForm
from course_discovery.apps.publisher.models import Course, CourseRun, Seat

# pylint: disable=attribute-defined-outside-init
class CreateCourseView(edit.CreateView):
    """ Create Course View."""
    model = Course
    form_class = CourseForm
    template_name = 'publisher/course_form.html'
    success_url = '.'

    def form_valid(self, form):
        self.object = form.save()
        return HttpResponseRedirect(self.get_success_url())


class UpdateCourseView(edit.UpdateView):
    """ Update Course View."""
    model = Course
    form_class = CourseForm
    template_name = 'publisher/course_form.html'
    success_url = '.'

    def form_valid(self, form):
        self.object = form.save()
        return HttpResponseRedirect(self.get_success_url())


class CreateCourseRunView(edit.CreateView):
    """ Create Course Run View."""
    model = CourseRun
    form_class = CourseRunForm
    template_name = 'publisher/course_run_form.html'
    success_url = '.'

    def form_valid(self, form):
        self.object = form.save()
        return HttpResponseRedirect(self.get_success_url())


class UpdateCourseRunView(edit.UpdateView):
    """ Update Course Run View."""
    model = CourseRun
    form_class = CourseRunForm
    template_name = 'publisher/course_run_form.html'
    success_url = '.'

    def form_valid(self, form):
        self.object = form.save()
        return HttpResponseRedirect(self.get_success_url())

