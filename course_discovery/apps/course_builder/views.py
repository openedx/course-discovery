"""
Course Builder views.
"""
from django.http import Http404
from django.views.generic import TemplateView
import waffle

from course_discovery.apps.course_metadata.models import Course


class CourseListing(TemplateView):
    """ Course listing view."""
    template_name = 'course_builder/course_listing.html'

    def get_context_data(self, **kwargs):
        context = super(CourseListing, self).get_context_data(**kwargs)

        context.update({
            'courses': self._get_courses(),
        })

        return context

    def get(self, request, *args, **kwargs):
        """ Get method for list page."""
        if not waffle.switch_is_active('enable_course_builder'):
            raise Http404
        return super(CourseListing, self).get(request, args, **kwargs)

    def _get_courses(self):
        """ Helper method to retrieve all courses."""
        return Course.objects.all()
