"""
Course publisher views.
"""
from django.http import HttpResponseRedirect
from django.views.generic import detail, edit, list
from course_discovery.apps.publisher.forms import CourseForm, CourseRunForm
from course_discovery.apps.publisher.models import Course, CourseRun
from course_discovery.apps.publisher.wrappers import CourseRunWrapper


class CourseRunListView(list.ListView):
    """ Create Course View."""
    template_name = 'publisher/course_runs_list.html'

    def get_queryset(self):
        return [
            CourseRunWrapper(course_run) for course_run in CourseRun.objects.select_related('course').all()
        ]


class CourseRunDetailView(detail.DetailView):
    """ Create Course View."""
    model = CourseRun
    template_name = 'publisher/course_run_detail.html'

    def get_context_data(self, **kwargs):
        context = super(CourseRunDetailView, self).get_context_data(**kwargs)
        context['object'] = CourseRunWrapper(context['object'])
        return context


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


class PrePublishView(detail.DetailView):
    """ Pre Publish View."""
    model = CourseRun
    template_name = 'publisher/pre_publish/home.html'

    def get_context_data(self, **kwargs):
        context = super(PrePublishView, self).get_context_data(**kwargs)
        context['object'] = CourseRunWrapper(context['object'])
        return context
