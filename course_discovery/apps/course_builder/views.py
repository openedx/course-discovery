"""
Course Builder views.
"""
from django.views.generic import TemplateView


class CourseListing(TemplateView):
    """ Course listing view."""
    template_name = 'course_builder/course_listing.html'

    def get_context_data(self, **kwargs):
        context = super(CourseListing, self).get_context_data(**kwargs)

        return context
