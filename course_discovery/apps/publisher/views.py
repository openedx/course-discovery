"""
Course publisher views.
"""
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.views.generic import View
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView, UpdateView
from django.views.generic.list import ListView
from django_fsm import TransitionNotAllowed

from course_discovery.apps.publisher.forms import CourseForm, CourseRunForm, SeatForm
from course_discovery.apps.publisher.models import Course, CourseRun, Seat
from course_discovery.apps.publisher.wrappers import CourseRunWrapper


SEATS_HIDDEN_FIELDS = ['price', 'currency', 'upgrade_deadline', 'credit_provider', 'credit_hours']


class CourseRunListView(ListView):
    """ Create Course View."""
    template_name = 'publisher/course_runs_list.html'

    def get_queryset(self):
        return [
            CourseRunWrapper(course_run) for course_run in CourseRun.objects.select_related('course').all()
        ]


class CourseRunDetailView(DetailView):
    """ Course Run Detail View."""
    model = CourseRun
    template_name = 'publisher/course_run_detail.html'

    def get_context_data(self, **kwargs):
        context = super(CourseRunDetailView, self).get_context_data(**kwargs)
        context['object'] = CourseRunWrapper(context['object'])
        context['comment_object'] = self.object.course
        return context


# pylint: disable=attribute-defined-outside-init
class CreateCourseView(CreateView):
    """ Create Course View."""
    model = Course
    form_class = CourseForm
    template_name = 'publisher/course_form.html'
    success_url = 'publisher:publisher_courses_edit'

    def form_valid(self, form):
        self.object = form.save()
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse(self.success_url, kwargs={'pk': self.object.id})


class UpdateCourseView(UpdateView):
    """ Update Course View."""
    model = Course
    form_class = CourseForm
    template_name = 'publisher/course_form.html'
    success_url = 'publisher:publisher_courses_edit'

    def form_valid(self, form):
        self.object = form.save()
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse(self.success_url, kwargs={'pk': self.object.id})

    def get_context_data(self, **kwargs):
        context = super(UpdateCourseView, self).get_context_data(**kwargs)
        context['comment_object'] = self.object
        return context


class CreateCourseRunView(CreateView):
    """ Create Course Run View."""
    model = CourseRun
    form_class = CourseRunForm
    template_name = 'publisher/course_run_form.html'
    success_url = 'publisher:publisher_course_runs_edit'

    def form_valid(self, form):
        self.object = form.save()
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse(self.success_url, kwargs={'pk': self.object.id})


class UpdateCourseRunView(UpdateView):
    """ Update Course Run View."""
    model = CourseRun
    form_class = CourseRunForm
    template_name = 'publisher/course_run_form.html'
    success_url = 'publisher:publisher_course_runs_edit'

    def get_context_data(self, **kwargs):
        context = super(UpdateCourseRunView, self).get_context_data(**kwargs)
        if not self.object:
            self.object = self.get_object()
        context['workflow_state'] = self.object.current_state
        context['comment_object'] = self.object
        return context

    def form_valid(self, form):
        self.object = form.save()
        self.object.change_state()
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse(self.success_url, kwargs={'pk': self.object.id})


class CreateSeatView(CreateView):
    """ Create Seat View."""
    model = Seat
    form_class = SeatForm
    template_name = 'publisher/seat_form.html'
    success_url = 'publisher:publisher_seats_edit'

    def get_context_data(self, **kwargs):
        context = super(CreateSeatView, self).get_context_data(**kwargs)
        context['hidden_fields'] = SEATS_HIDDEN_FIELDS
        return context

    def form_valid(self, form):
        self.object = form.save()
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse(self.success_url, kwargs={'pk': self.object.id})


class UpdateSeatView(UpdateView):
    """ Update Seat View."""
    model = Seat
    form_class = SeatForm
    template_name = 'publisher/seat_form.html'
    success_url = 'publisher:publisher_seats_edit'

    def get_context_data(self, **kwargs):
        context = super(UpdateSeatView, self).get_context_data(**kwargs)
        context['hidden_fields'] = SEATS_HIDDEN_FIELDS
        context['comment_object'] = self.object
        return context

    def form_valid(self, form):
        self.object = form.save()
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse(self.success_url, kwargs={'pk': self.object.id})


class ChangeStateView(View):
    """ Change Workflow State View"""

    def post(self, request, course_run_id):
        state = request.POST.get('state')
        try:
            course_run = CourseRun.objects.get(id=course_run_id)
            course_run.change_state(target=state)
            messages.success(
                request, 'Content moved to `{state}` successfully.'.format(state=course_run.current_state),
            )
            return HttpResponseRedirect(reverse('publisher:publisher_course_run_detail', kwargs={'pk': course_run_id}))
        except (CourseRun.DoesNotExist, TransitionNotAllowed):
            messages.error(request, 'There was an error in changing state.')
            return HttpResponseRedirect(reverse('publisher:publisher_course_run_detail', kwargs={'pk': course_run_id}))
