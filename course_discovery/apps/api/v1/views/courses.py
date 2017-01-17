from django.db.models.functions import Lower
from rest_framework import viewsets
from rest_framework.filters import DjangoFilterBackend
from rest_framework.permissions import IsAuthenticated

from course_discovery.apps.api import filters, serializers
from course_discovery.apps.api.pagination import ProxiedPagination
from course_discovery.apps.api.v1.views import prefetch_related_objects_for_courses, get_query_param
from course_discovery.apps.course_metadata.constants import COURSE_ID_REGEX
from course_discovery.apps.course_metadata.models import Course


# pylint: disable=no-member
class CourseViewSet(viewsets.ReadOnlyModelViewSet):
    """ Course resource. """
    filter_backends = (DjangoFilterBackend,)
    filter_class = filters.CourseFilter
    lookup_field = 'key'
    lookup_value_regex = COURSE_ID_REGEX
    queryset = Course.objects.all()
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.CourseWithProgramsSerializer

    # Explicitly support PageNumberPagination and LimitOffsetPagination. Future
    # versions of this API should only support the system default, PageNumberPagination.
    pagination_class = ProxiedPagination

    def get_queryset(self):
        q = self.request.query_params.get('q', None)

        if q:
            queryset = Course.search(q)
        else:
            queryset = super(CourseViewSet, self).get_queryset()
            queryset = prefetch_related_objects_for_courses(queryset)

        return queryset.order_by(Lower('key'))

    def get_serializer_context(self, *args, **kwargs):
        context = super().get_serializer_context(*args, **kwargs)
        context.update({
            'exclude_utm': get_query_param(self.request, 'exclude_utm'),
            'include_deleted_programs': get_query_param(self.request, 'include_deleted_programs'),
            'marketable_course_runs_only': get_query_param(self.request, 'marketable_course_runs_only'),
            'published_course_runs_only': get_query_param(self.request, 'published_course_runs_only'),
        })

        return context

    def list(self, request, *args, **kwargs):
        """ List all courses.
         ---
        parameters:
            - name: exclude_utm
              description: Exclude UTM parameters from marketing URLs.
              required: false
              type: integer
              paramType: query
              multiple: false
            - name: include_deleted_programs
              description: Will include deleted programs in the associated programs array
              required: false
              type: integer
              paramType: query
              multiple: false
            - name: keys
              description: Filter by keys (comma-separated list)
              required: false
              type: string
              paramType: query
              multiple: false
            - name: marketable_course_runs_only
              description: Restrict returned course runs to those that are published, have seats,
                and can still be enrolled in.
              required: false
              type: integer
              paramType: query
              mulitple: false
            - name: published_course_runs_only
              description: Filter course runs by published ones only
              required: false
              type: integer
              paramType: query
              mulitple: false
            - name: q
              description: Elasticsearch querystring query. This filter takes precedence over other filters.
              required: false
              type: string
              paramType: query
              multiple: false
        """
        return super(CourseViewSet, self).list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """ Retrieve details for a course. """
        return super(CourseViewSet, self).retrieve(request, *args, **kwargs)
