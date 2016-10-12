import datetime
import logging
import os
from io import StringIO

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import transaction
from django.db.models.functions import Lower
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_haystack.mixins import FacetMixin
from drf_haystack.viewsets import HaystackViewSet
from dry_rest_permissions.generics import DRYPermissions
from edx_rest_framework_extensions.permissions import IsSuperuser
from haystack.inputs import AutoQuery
from haystack.query import SQ
from rest_framework import status, viewsets
from rest_framework.decorators import detail_route, list_route
from rest_framework.exceptions import PermissionDenied, ParseError
from rest_framework.filters import DjangoFilterBackend
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from course_discovery.apps.api import filters
from course_discovery.apps.api import serializers
from course_discovery.apps.api.exceptions import InvalidPartnerError
from course_discovery.apps.api.pagination import PageNumberPagination
from course_discovery.apps.api.renderers import AffiliateWindowXMLRenderer, CourseRunCSVRenderer
from course_discovery.apps.api.utils import cast2int
from course_discovery.apps.catalogs.models import Catalog
from course_discovery.apps.core.utils import SearchQuerySetWrapper
from course_discovery.apps.course_metadata.constants import COURSE_ID_REGEX, COURSE_RUN_ID_REGEX
from course_discovery.apps.course_metadata.models import Course, CourseRun, Partner, Program, Seat

logger = logging.getLogger(__name__)
User = get_user_model()


def get_query_param(request, name):
    """
    Get a query parameter and cast it to an integer.
    """
    return cast2int(request.query_params.get(name), name)


def prefetch_related_objects_for_courses(queryset):
    """
    Pre-fetches the related objects that will be serialized with a `Course`.

    Pre-fetching allows us to consolidate our database queries rather than run
    thousands of queries as we serialize the data. For details, see the links below:

        - https://docs.djangoproject.com/en/1.10/ref/models/querysets/#select-related
        - https://docs.djangoproject.com/en/1.10/ref/models/querysets/#prefetch-related

    Args:
        queryset (QuerySet): original query

    Returns:
        QuerySet
    """
    _prefetch_fields = serializers.PREFETCH_FIELDS
    _select_related_fields = serializers.SELECT_RELATED_FIELDS

    # Prefetch the data for the related course runs
    course_run_prefetch_fields = _prefetch_fields['course_run'] + _select_related_fields['course_run']
    course_run_prefetch_fields = ['course_runs__' + field for field in course_run_prefetch_fields]
    queryset = queryset.prefetch_related(*course_run_prefetch_fields)

    queryset = queryset.select_related(*_select_related_fields['course'])
    queryset = queryset.prefetch_related(*_prefetch_fields['course'])
    return queryset


# pylint: disable=no-member
class CatalogViewSet(viewsets.ModelViewSet):
    """ Catalog resource. """

    filter_backends = (filters.PermissionsFilter,)
    lookup_field = 'id'
    permission_classes = (DRYPermissions,)
    queryset = Catalog.objects.all()
    serializer_class = serializers.CatalogSerializer

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """ Create a new catalog. """
        data = request.data.copy()
        usernames = request.data.get('viewers', ())

        # Add support for parsing a comma-separated list from Swagger
        if isinstance(usernames, str):
            usernames = usernames.split(',')
            data.setlist('viewers', usernames)

        # Ensure the users exist
        for username in usernames:
            User.objects.get_or_create(username=username)

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def destroy(self, request, *args, **kwargs):
        """ Destroy a catalog. """
        return super(CatalogViewSet, self).destroy(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        """ Retrieve a list of all catalogs.
        ---
        parameters:
            - name: username
              description: User whose catalogs should be retrieved.
              required: false
              type: string
              paramType: query
              multiple: false
        """
        return super(CatalogViewSet, self).list(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        """ Update one, or more, fields for a catalog. """
        return super(CatalogViewSet, self).partial_update(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """ Retrieve details for a catalog. """
        return super(CatalogViewSet, self).retrieve(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """ Update a catalog. """
        return super(CatalogViewSet, self).update(request, *args, **kwargs)

    @detail_route()
    def courses(self, request, id=None):  # pylint: disable=redefined-builtin,unused-argument
        """
        Retrieve the list of courses contained within this catalog.

        Only courses with active course runs are returned. A course run is considered active if it is currently
        open for enrollment, or will open in the future.
        ---
        serializer: serializers.CourseSerializerExcludingClosedRuns
        """

        catalog = self.get_object()
        queryset = catalog.courses().active()
        queryset = prefetch_related_objects_for_courses(queryset)

        page = self.paginate_queryset(queryset)
        serializer = serializers.CourseSerializerExcludingClosedRuns(page, many=True, context={'request': request})
        return self.get_paginated_response(serializer.data)

    @detail_route()
    def contains(self, request, id=None):  # pylint: disable=redefined-builtin,unused-argument
        """
        Determine if this catalog contains the provided courses.

        A dictionary mapping course IDs to booleans, indicating course presence, will be returned.
        ---
        serializer: serializers.ContainedCoursesSerializer
        parameters:
            - name: course_id
              description: Course IDs to check for existence in the Catalog.
              required: true
              type: string
              paramType: query
              multiple: true
        """
        course_ids = request.query_params.get('course_id')
        course_ids = course_ids.split(',')

        catalog = self.get_object()
        courses = catalog.contains(course_ids)

        instance = {'courses': courses}
        serializer = serializers.ContainedCoursesSerializer(instance)
        return Response(serializer.data)

    @detail_route()
    def csv(self, request, id=None):  # pylint: disable=redefined-builtin,unused-argument
        """
        Retrieve a CSV containing the course runs contained within this catalog.

        Only active course runs are returned. A course run is considered active if it is currently
        open for enrollment, or will be open for enrollment in the future.
        ---
        serializer: serializers.FlattenedCourseRunWithCourseSerializer
        """
        catalog = self.get_object()
        courses = catalog.courses()
        course_runs = CourseRun.objects.filter(course__in=courses).active().marketable()

        # We use select_related and prefetch_related to decrease our database query count
        course_runs = course_runs.select_related(*serializers.SELECT_RELATED_FIELDS['course_run'])
        prefetch_fields = ['course__' + field for field in serializers.PREFETCH_FIELDS['course']]
        prefetch_fields += serializers.PREFETCH_FIELDS['course_run']
        course_runs = course_runs.prefetch_related(*prefetch_fields)

        serializer = serializers.FlattenedCourseRunWithCourseSerializer(
            course_runs, many=True, context={'request': request}
        )
        data = CourseRunCSVRenderer().render(serializer.data)

        response = HttpResponse(data, content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="catalog_{id}_{date}.csv"'.format(
            id=id, date=datetime.datetime.utcnow().strftime('%Y-%m-%d-%H-%M')
        )
        return response


class CourseViewSet(viewsets.ReadOnlyModelViewSet):
    """ Course resource. """
    filter_backends = (DjangoFilterBackend,)
    filter_class = filters.CourseFilter
    lookup_field = 'key'
    lookup_value_regex = COURSE_ID_REGEX
    queryset = Course.objects.all()
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.CourseWithProgramsSerializer

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
        })

        return context

    def list(self, request, *args, **kwargs):
        """ List all courses.
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
            - name: exclude_utm
              description: Exclude UTM parameters from marketing URLs.
              required: false
              type: integer
              paramType: query
              multiple: false
        """
        return super(CourseViewSet, self).list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """ Retrieve details for a course. """
        return super(CourseViewSet, self).retrieve(request, *args, **kwargs)


class CourseRunViewSet(viewsets.ReadOnlyModelViewSet):
    """ CourseRun resource. """
    filter_backends = (DjangoFilterBackend,)
    filter_class = filters.CourseRunFilter
    lookup_field = 'key'
    lookup_value_regex = COURSE_RUN_ID_REGEX
    queryset = CourseRun.objects.all().order_by(Lower('key'))
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.CourseRunWithProgramsSerializer

    def _get_partner(self):
        """ Return the partner for the code passed in or the default partner """
        partner_code = self.request.query_params.get('partner')
        if partner_code:
            try:
                partner = Partner.objects.get(short_code=partner_code)
            except Partner.DoesNotExist:
                raise InvalidPartnerError('Unknown Partner')
        else:
            partner = Partner.objects.get(id=settings.DEFAULT_PARTNER_ID)

        return partner

    def get_queryset(self):
        q = self.request.query_params.get('q', None)
        partner = self._get_partner()

        if q:
            qs = SearchQuerySetWrapper(CourseRun.search(q).filter(partner=partner.short_code))
            # This is necessary to avoid issues with the filter backend.
            qs.model = self.queryset.model
            return qs
        else:
            queryset = super(CourseRunViewSet, self).get_queryset().filter(course__partner=partner)
            queryset = queryset.select_related(*serializers.SELECT_RELATED_FIELDS['course_run'])
            queryset = queryset.prefetch_related(*serializers.PREFETCH_FIELDS['course_run'])
            return queryset

    def get_serializer_context(self, *args, **kwargs):
        context = super().get_serializer_context(*args, **kwargs)
        context.update({
            'exclude_utm': get_query_param(self.request, 'exclude_utm'),
        })

        return context

    def list(self, request, *args, **kwargs):
        """ List all courses runs.
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
        """
        return super(CourseRunViewSet, self).list(request, *args, **kwargs)

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
        partner = self._get_partner()

        if query and course_run_ids:
            course_run_ids = course_run_ids.split(',')
            course_runs = CourseRun.search(query).filter(partner=partner.short_code).filter(key__in=course_run_ids). \
                values_list('key', flat=True)
            contains = {course_run_id: course_run_id in course_runs for course_run_id in course_run_ids}

            instance = {'course_runs': contains}
            serializer = serializers.ContainedCourseRunsSerializer(instance)
            return Response(serializer.data)
        return Response(status=status.HTTP_400_BAD_REQUEST)


class ProgramViewSet(viewsets.ReadOnlyModelViewSet):
    """ Program resource. """
    lookup_field = 'uuid'
    lookup_value_regex = '[0-9a-f-]+'
    permission_classes = (IsAuthenticated,)
    filter_backends = (DjangoFilterBackend,)
    filter_class = filters.ProgramFilter

    def get_serializer_class(self):
        if self.action == 'list':
            return serializers.MinimalProgramSerializer

        return serializers.ProgramSerializer

    def get_queryset(self):
        # This method prevents prefetches on the program queryset from "stacking,"
        # which happens when the queryset is stored in a class property.
        return self.get_serializer_class().prefetch_queryset()

    def get_serializer_context(self, *args, **kwargs):
        context = super().get_serializer_context(*args, **kwargs)
        context.update({
            'published_course_runs_only': get_query_param(self.request, 'published_course_runs_only'),
            'exclude_utm': get_query_param(self.request, 'exclude_utm'),
        })

        return context

    def list(self, request, *args, **kwargs):
        """ List all programs.
        ---
        parameters:
            - name: partner
              description: Filter by partner
              required: false
              type: string
              paramType: query
              multiple: false
            - name: marketable
              description: Retrieve marketable programs. A program is considered marketable if it is active
                and has a marketing slug.
              required: false
              type: integer
              paramType: query
              multiple: false
            - name: published_course_runs_only
              description: Filter course runs by published ones only
              required: false
              type: integer
              paramType: query
              mulitple: false
            - name: exclude_utm
              description: Exclude UTM parameters from marketing URLs.
              required: false
              type: integer
              paramType: query
              multiple: false
        """
        return super(ProgramViewSet, self).list(request, *args, **kwargs)


class ManagementViewSet(viewsets.ViewSet):
    permission_classes = (IsSuperuser,)

    @list_route(methods=['post'])
    def refresh_course_metadata(self, request):
        """ Refresh the course metadata from external data sources.
        ---
        parameters:
            - name: access_token
              description: OAuth access token to use in lieu of that issued to the service.
              required: false
              type: string
              paramType: form
              multiple: false
        """
        access_token = request.data.get('access_token')
        kwargs = {'access_token': access_token} if access_token else {}
        name = 'refresh_course_metadata'

        output = self.run_command(request, name, **kwargs)

        return Response(output, content_type='text/plain')

    @list_route(methods=['post'])
    def update_index(self, request):
        """ Update the search index. """
        name = 'update_index'

        output = self.run_command(request, name)

        return Response(output, content_type='text/plain')

    def run_command(self, request, name, **kwargs):
        # Capture all output and logging
        out = StringIO()
        err = StringIO()
        log = StringIO()

        root_logger = logging.getLogger()
        log_handler = logging.StreamHandler(log)
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        log_handler.setFormatter(formatter)
        root_logger.addHandler(log_handler)

        logger.info('Running [%s] per request of [%s]...', name, request.user.username)
        call_command(name, settings=os.environ['DJANGO_SETTINGS_MODULE'], stdout=out, stderr=err, **kwargs)

        # Format the output for display
        output = 'STDOUT\n{out}\n\nSTDERR\n{err}\n\nLOG\n{log}'.format(out=out.getvalue(), err=err.getvalue(),
                                                                       log=log.getvalue())
        return output


class AffiliateWindowViewSet(viewsets.ViewSet):
    """ AffiliateWindow Resource. """
    permission_classes = (IsAuthenticated,)
    renderer_classes = (AffiliateWindowXMLRenderer,)
    serializer_class = serializers.AffiliateWindowSerializer

    def retrieve(self, request, pk=None):  # pylint: disable=redefined-builtin,unused-argument
        """
        Return verified and professional seats of courses against provided catalog id.
        ---
        produces:
            - application/xml
        """

        catalog = get_object_or_404(Catalog, pk=pk)

        if not catalog.has_object_read_permission(request):
            raise PermissionDenied

        courses = catalog.courses()
        course_runs = CourseRun.objects.filter(course__in=courses).active().marketable()
        seats = Seat.objects.filter(type__in=[Seat.VERIFIED, Seat.PROFESSIONAL]).filter(course_run__in=course_runs)
        seats = seats.select_related('course_run').prefetch_related('course_run__course', 'course_run__course__partner')

        serializer = serializers.AffiliateWindowSerializer(seats, many=True)
        return Response(serializer.data)


class BaseHaystackViewSet(FacetMixin, HaystackViewSet):
    document_uid_field = 'key'
    facet_filter_backends = [filters.HaystackFacetFilterWithQueries, filters.HaystackFilter]
    load_all = True
    lookup_field = 'key'
    permission_classes = (IsAuthenticated,)

    # NOTE: We use PageNumberPagination because drf-haystack's facet serializer relies on the page_query_param
    # attribute, and it is more appropriate for search results than our default limit-offset pagination.
    pagination_class = PageNumberPagination

    def list(self, request, *args, **kwargs):
        """
        Search.
        ---
        parameters:
            - name: q
              description: Search text
              paramType: query
              type: string
              required: false
        """
        return super(BaseHaystackViewSet, self).list(request, *args, **kwargs)

    @list_route(methods=['get'], url_path='facets')
    def facets(self, request):
        """
        Returns faceted search results
        ---
        parameters:
            - name: q
              description: Search text
              paramType: query
              type: string
              required: false
            - name: selected_facets
              description: Field facets
              paramType: query
              allowMultiple: true
              type: array
              items:
                pytype: str
              required: false
            - name: selected_query_facets
              description: Query facets
              paramType: query
              allowMultiple: true
              type: array
              items:
                pytype: str
              required: false
        """
        return super(BaseHaystackViewSet, self).facets(request)

    def filter_facet_queryset(self, queryset):
        queryset = super().filter_facet_queryset(queryset)

        q = self.request.query_params.get('q')
        if q:
            queryset = queryset.filter(SQ(text=AutoQuery(q)) | SQ(title=AutoQuery(q)))

        facet_serializer_cls = self.get_facet_serializer_class()
        field_queries = getattr(facet_serializer_cls.Meta, 'field_queries', {})

        # Ensure we only return published, non-hidden items
        queryset = queryset.filter(published=True).exclude(hidden=True)

        for facet in self.request.query_params.getlist('selected_query_facets'):
            query = field_queries.get(facet)

            if not query:
                raise ParseError('The selected query facet [{facet}] is not valid.'.format(facet=facet))

            queryset = queryset.raw_search(query['query'])

        return queryset


class CourseSearchViewSet(BaseHaystackViewSet):
    facet_serializer_class = serializers.CourseFacetSerializer
    index_models = (Course,)
    serializer_class = serializers.CourseSearchSerializer


class CourseRunSearchViewSet(BaseHaystackViewSet):
    facet_serializer_class = serializers.CourseRunFacetSerializer
    index_models = (CourseRun,)
    serializer_class = serializers.CourseRunSearchSerializer


class ProgramSearchViewSet(BaseHaystackViewSet):
    document_uid_field = 'uuid'
    lookup_field = 'uuid'
    facet_serializer_class = serializers.ProgramFacetSerializer
    index_models = (Program,)
    serializer_class = serializers.ProgramSearchSerializer


class AggregateSearchViewSet(BaseHaystackViewSet):
    """ Search all content types. """
    facet_serializer_class = serializers.AggregateFacetSearchSerializer
    serializer_class = serializers.AggregateSearchSerializer
