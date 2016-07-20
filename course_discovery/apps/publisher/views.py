"""
Course publisher views.
"""
from django.views.generic import TemplateView
from course_discovery.apps.publisher.forms import CourseForm, CourseRunForm


class CourseAboutView(TemplateView):
    """ Course About View."""
    template_name = 'publisher/course_run_form.html'

    def get_context_data(self, **kwargs):
        context = super(CourseAboutView, self).get_context_data(**kwargs)
        if self.request.POST:
            context['forms'] = [CourseForm(self.request.POST), CourseRunForm(self.request.POST)]
        else:
            context['forms'] = [CourseForm(), CourseRunForm()]
        return context

    def post(self, request, *args, **kwargs):
        course_form = CourseForm(request.POST)
        course_run_form = CourseRunForm(request.POST)

        if course_form.is_valid() and course_run_form.is_valid():
            pass

        return self.render_to_response(context=self.get_context_data(**kwargs))
