"""
Publisher views.
"""
from django.http import Http404
from django.views.generic import TemplateView
import waffle

from course_discovery.apps.course_metadata.models import CourseRun
from course_discovery.apps.publisher.models import Status


class UnpublishedCourseListing(TemplateView):
    """ Unpublished Course listing view."""
    template_name = 'publisher/unpublished_courses.html'

    def get_context_data(self, **kwargs):
        context = super(UnpublishedCourseListing, self).get_context_data(**kwargs)

        context.update({
            'courses_runs': self._get_unpublished_course_runs(),
        })

        return context

    def get(self, request, *args, **kwargs):
        """ Get method for list page."""
        if not waffle.switch_is_active('enable_publisher'):
            raise Http404
        return super(UnpublishedCourseListing, self).get(request, args, **kwargs)

    def _get_unpublished_course_runs(self):
        """ Helper method to retrieve all course runs whose status is not published."""
        return CourseRun.objects.filter(status__name__in=Status.NON_PUBLISHED_STATUS)
