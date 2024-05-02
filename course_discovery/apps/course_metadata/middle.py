
import json
from django.http import *
from course_discovery.apps.course_metadata.models import *
from course_discovery.apps.course_metadata.managers import *

class MagicMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # One-time configuration and initialization.

    def __call__(self, request):
        # Code to be executed for each request before
        # the view (and later middleware) are called.

        method = request.method


        if method == 'GET' and not request.GET.get('restriction_type', None):
            CourseRun._meta.local_managers.clear()
            CourseRun.add_to_class('everything', EverythingRunManagerWithoutRestriction() )
            CourseRun.add_to_class('objects', DraftRunManagerWithoutRestriction.from_queryset(CourseRunQuerySet)())

        response = self.get_response(request)

        # Code to be executed for each request/response after
        # the view is called.
        if method == 'GET':
            CourseRun._meta.local_managers.clear()
            CourseRun.add_to_class('everything', CourseRunQuerySet.as_manager() )
            CourseRun.add_to_class('objects', DraftManager.from_queryset(CourseRunQuerySet)())

        return response
