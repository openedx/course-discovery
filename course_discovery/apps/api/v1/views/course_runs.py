from django.db.models.functions import Lower
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import list_route
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import DjangoModelPermissions, IsAuthenticated
from rest_framework.response import Response

from course_discovery.apps.api import filters, serializers
from course_discovery.apps.api.pagination import ProxiedPagination
from course_discovery.apps.api.utils import get_query_param
from course_discovery.apps.api.v1.views import PartnerMixin
from course_discovery.apps.core.utils import SearchQuerySetWrapper
from course_discovery.apps.course_metadata.constants import COURSE_RUN_ID_REGEX
from course_discovery.apps.course_metadata.models import CourseRun


# pylint: disable=no-member
class CourseRunViewSet(PartnerMixin, viewsets.ModelViewSet):
    """ CourseRun resource. """
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filter_class = filters.CourseRunFilter
    lookup_field = 'key'
    lookup_value_regex = COURSE_RUN_ID_REGEX
    ordering_fields = ('start',)
    permission_classes = (IsAuthenticated, DjangoModelPermissions)
    queryset = CourseRun.objects.all().order_by(Lower('key'))
    serializer_class = serializers.CourseRunWithProgramsSerializer

    # Explicitly support PageNumberPagination and LimitOffsetPagination. Future
    # versions of this API should only support the system default, PageNumberPagination.
    pagination_class = ProxiedPagination

    def get_queryset(self):
        """ List one course run
        ---
        parameters:
            - name: include_deleted_programs
              description: Will include deleted programs in the associated programs array
              required: false
              type: integer
              paramType: query
              multiple: false
        """
        q = self.request.query_params.get('q')
        partner = self.get_partner()

        if q:
            qs = SearchQuerySetWrapper(CourseRun.search(q).filter(partner=partner.short_code))
            # This is necessary to avoid issues with the filter backend.
            qs.model = self.queryset.model
            return qs
        else:
            queryset = super(CourseRunViewSet, self).get_queryset().filter(course__partner=partner)
            return self.get_serializer_class().prefetch_queryset(queryset=queryset)

    def get_serializer_context(self, *args, **kwargs):
        context = super().get_serializer_context(*args, **kwargs)
        context.update({
            'exclude_utm': get_query_param(self.request, 'exclude_utm'),
            'include_deleted_programs': get_query_param(self.request, 'include_deleted_programs'),
            'include_unpublished_programs': get_query_param(self.request, 'include_unpublished_programs'),
        })

        return context

    def list(self, request, *args, **kwargs):
        """ List all course runs.
        ---
        parameters:
            - name: q
              description: Elasticsearch querystring query. This filter takes precedence over other filters.
              required: false
              type: string
              paramType: query
              multiple: false
            - name: keys
              description: Filter by keys (comma-separated list)
              required: false
              type: string
              paramType: query
              multiple: false
            - name: partner
              description: Filter by partner
              required: false
              type: string
              paramType: query
              multiple: false
            - name: hidden
              description: Filter based on wether the course run is hidden from search.
              required: false
              type: Boolean
              paramType: query
              multiple: false
            - name: active
              description: Retrieve active course runs. A course is considered active if its end date has not passed,
                and it is open for enrollment.
              required: false
              type: integer
              paramType: query
              multiple: false
            - name: marketable
              description: Retrieve marketable course runs. A course run is considered marketable if it has a
                marketing slug.
              required: false
              type: integer
              paramType: query
              multiple: false
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
            - name: include_unpublished_programs
              description: Will include unpublished programs in the associated programs array
              required: false
              type: integer
              paramType: query
              multiple: false
        """
        return super(CourseRunViewSet, self).list(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        """ Update one, or more, fields for a course run. """
        return super(CourseRunViewSet, self).partial_update(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """ Retrieve details for a course run. """
        return super(CourseRunViewSet, self).retrieve(request, *args, **kwargs)

    @list_route()
    def contains(self, request):
        """
        Determine if course runs are found in the query results.

        A dictionary mapping course run keys to booleans,
        indicating course run presence, will be returned.
        ---
        serializer: serializers.ContainedCourseRunsSerializer
        parameters:
            - name: query
              description: Elasticsearch querystring query
              required: true
              type: string
              paramType: query
              multiple: false
            - name: course_run_ids
              description: Comma-separated list of course run IDs
              required: true
              type: string
              paramType: query
              multiple: true
            - name: partner
              description: Filter by partner
              required: false
              type: string
              paramType: query
              multiple: false
        """
        query = request.GET.get('query')
        course_run_ids = request.GET.get('course_run_ids')
        partner = self.get_partner()

        if query and course_run_ids:
            course_run_ids = course_run_ids.split(',')
            course_runs = CourseRun.search(query).filter(partner=partner.short_code).filter(key__in=course_run_ids). \
                values_list('key', flat=True)
            contains = {course_run_id: course_run_id in course_runs for course_run_id in course_run_ids}

            instance = {'course_runs': contains}
            serializer = serializers.ContainedCourseRunsSerializer(instance)
            return Response(serializer.data)
        return Response(status=status.HTTP_400_BAD_REQUEST)
