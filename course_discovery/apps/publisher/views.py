"""
Course Builder views.
"""
from django.http import Http404
from django.shortcuts import get_object_or_404
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


class CourseDetailPrepublish(TemplateView):
    """ Unpublished Course listing view."""
    template_name = 'publisher/prepublish.html'

    def get_context_data(self, **kwargs):
        context = super(CourseDetailPrepublish, self).get_context_data(**kwargs)

        context.update({
            'course_run': self.course_run,
        })

        return context

    def get(self, request, course_run_key, *args, **kwargs):
        """ Get method for course run prepublish page."""
        if not waffle.switch_is_active('enable_publisher'):
            raise Http404

        self.course_run = get_object_or_404(CourseRun, key=course_run_key)
        return super(CourseDetailPrepublish, self).get(request, args, **kwargs)
