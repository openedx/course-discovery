"""
Course publisher views.
"""
from django.db import transaction
from django.views.generic import edit, TemplateView
from course_discovery.apps.publisher.forms import CourseForm, CourseRunForm, SeatForm
from course_discovery.apps.publisher.models import Course, CourseRun, Seat


class CreateCourseView(TemplateView):
    """ Create Course View."""
    template_name = 'publisher/course_run_form.html'

    def get_context_data(self, **kwargs):
        context = super(CreateCourseView, self).get_context_data(**kwargs)
        if 'forms' not in context:
            context['forms'] = [CourseForm(), CourseRunForm(), SeatForm()]
        return context

    @transaction.atomic
    def post(self, request):
        course_form = CourseForm(request.POST)
        course_run_form = CourseRunForm(request.POST)
        course_seat_form = SeatForm(request.POST)

        if course_form.is_valid() and course_run_form.is_valid() and course_seat_form.is_valid():
            course = course_form.save()
            course_run = course_run_form.save(commit=False)
            course_run.course = course
            course_run.save()
            course_seat = course_seat_form.save(commit=False)
            course_seat.course_run = course_run
            course_seat.save()

        return self.render_to_response(
            context=self.get_context_data(forms=[course_form, course_run_form, course_seat_form])
        )


# pylint: disable=attribute-defined-outside-init
class UpdateCourseView(edit.UpdateView):
    """ Update Course View."""
    model = Course
    fields = '__all__'
    template_name = 'publisher/course_run_form.html'

    def get_context_data(self, **kwargs):
        context = super(UpdateCourseView, self).get_context_data(**kwargs)
        self.object = self.get_object()
        course = Course.objects.get(id=self.object.id)
        course_run = CourseRun.objects.get(course=course)
        course_seat = Seat.objects.get(course_run=course_run)
        if 'forms' not in context:
            context['forms'] = [
                CourseForm(instance=course),
                CourseRunForm(instance=course_run),
                SeatForm(instance=course_seat)
            ]
        return context

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        course = Course.objects.get(id=self.object.id)
        course_run = CourseRun.objects.get(course=course)
        course_seat = Seat.objects.get(course_run=course_run)
        course_form = CourseForm(request.POST, instance=course)
        course_run_form = CourseRunForm(request.POST, instance=course_run)
        course_seat_form = SeatForm(request.POST, instance=course_seat)

        if course_form.is_valid() and course_run_form.is_valid() and course_seat_form.is_valid():
            course_form.save()
            course_run_form.save()
            course_seat_form.save()

        return self.render_to_response(
            context=self.get_context_data(forms=[course_form, course_run_form, course_seat_form])
        )
