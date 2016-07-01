import datetime
import logging
import os
from io import StringIO

import pytz
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import transaction
from django.db.models import Q
from django.db.models.functions import Lower
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_haystack.filters import HaystackFilter, HaystackFacetFilter
from drf_haystack.mixins import FacetMixin
from drf_haystack.viewsets import HaystackViewSet
from dry_rest_permissions.generics import DRYPermissions
from edx_rest_framework_extensions.permissions import IsSuperuser
from rest_framework import status, viewsets
from rest_framework.decorators import detail_route, list_route
from rest_framework.exceptions import PermissionDenied, ParseError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from course_discovery.apps.api import serializers
from course_discovery.apps.api.filters import PermissionsFilter
from course_discovery.apps.api.pagination import PageNumberPagination
from course_discovery.apps.api.renderers import AffiliateWindowXMLRenderer, CourseRunCSVRenderer
from course_discovery.apps.catalogs.models import Catalog
from course_discovery.apps.core.utils import SearchQuerySetWrapper
from course_discovery.apps.course_metadata.constants import COURSE_ID_REGEX, COURSE_RUN_ID_REGEX
from course_discovery.apps.course_metadata.models import Course, CourseRun, Seat

logger = logging.getLogger(__name__)
User = get_user_model()


# pylint: disable=no-member
class CatalogViewSet(viewsets.ModelViewSet):
    """ Catalog resource. """

    filter_backends = (PermissionsFilter,)
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
        courses = catalog.courses().active()
        course_runs = []

        for course in courses:
            active_course_runs = course.active_course_runs
            for acr in active_course_runs:
                course_runs.append(acr)

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
    lookup_field = 'key'
    lookup_value_regex = COURSE_ID_REGEX
    queryset = Course.objects.all()
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.CourseSerializer

    def get_queryset(self):
        q = self.request.query_params.get('q', None)

        if q:
            queryset = Course.search(q)
        else:
            queryset = super(CourseViewSet, self).get_queryset()

        return queryset.order_by(Lower('key'))

    def list(self, request, *args, **kwargs):
        """ List all courses.
        ---
        parameters:
            - name: q
              description: Elasticsearch querystring query
              required: false
              type: string
              paramType: query
              multiple: false
        """
        return super(CourseViewSet, self).list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """ Retrieve details for a course. """
        return super(CourseViewSet, self).retrieve(request, *args, **kwargs)


class CourseRunViewSet(viewsets.ReadOnlyModelViewSet):
    """ CourseRun resource. """
    lookup_field = 'key'
    lookup_value_regex = COURSE_RUN_ID_REGEX
    queryset = CourseRun.objects.all().order_by(Lower('key'))
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.CourseRunSerializer

    def get_queryset(self):
        q = self.request.query_params.get('q', None)
        if q:
            return SearchQuerySetWrapper(CourseRun.search(q))
        else:
            return super(CourseRunViewSet, self).get_queryset()

    def list(self, request, *args, **kwargs):
        """ List all courses runs.
        ---
        parameters:
            - name: q
              description: Elasticsearch querystring query
              required: false
              type: string
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
        """
        query = request.GET.get('query')
        course_run_ids = request.GET.get('course_run_ids')

        if query and course_run_ids:
            course_runs = CourseRun.search(query)
            contains = {course_run_id: False for course_run_id in course_run_ids.split(',')}

            for course_run in course_runs:
                contains[course_run.key] = True

            instance = {'course_runs': contains}
            serializer = serializers.ContainedCourseRunsSerializer(instance)
            return Response(serializer.data)
        return Response(status=status.HTTP_400_BAD_REQUEST)


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

        courses = catalog.courses().active()

        seats = Seat.objects.filter(
            (Q(course_run__end__gte=datetime.datetime.now(pytz.UTC)) | Q(course_run__end__isnull=True)) &
            Q(course_run__course__in=courses) & Q(type__in=[Seat.VERIFIED, Seat.PROFESSIONAL]) &
            (Q(course_run__enrollment_end__isnull=True) |
             Q(course_run__enrollment_end__gte=datetime.datetime.now(pytz.UTC)))
        )

        serializer = serializers.AffiliateWindowSerializer(seats, many=True)
        return Response(serializer.data)


class BaseCourseHaystackViewSet(FacetMixin, HaystackViewSet):
    document_uid_field = 'key'
    facet_filter_backends = [HaystackFacetFilter, HaystackFilter]
    load_all = True
    lookup_field = 'key'
    permission_classes = (IsAuthenticated,)

    # NOTE: We use PageNumberPagination because drf-haytack's facet serializer relies on the page_query_param
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
        return super(BaseCourseHaystackViewSet, self).list(request, *args, **kwargs)

    @list_route(methods=["get"], url_path="facets")
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
        return super(BaseCourseHaystackViewSet, self).facets(request)

    def filter_facet_queryset(self, queryset):
        queryset = super(BaseCourseHaystackViewSet, self).filter_facet_queryset(queryset)

        facet_serializer_cls = self.get_facet_serializer_class()
        field_queries = facet_serializer_cls.Meta.field_queries

        for facet in self.request.query_params.getlist('selected_query_facets'):
            query = field_queries.get(facet)

            if not query:
                raise ParseError('The selected query facet [{facet}] is not valid.'.format(facet=facet))

            queryset = queryset.raw_search(query['query'])

        return queryset


class CourseSearchViewSet(BaseCourseHaystackViewSet):
    facet_serializer_class = serializers.CourseFacetSerializer
    index_models = (Course,)
    serializer_class = serializers.CourseSearchSerializer


class CourseRunSearchViewSet(BaseCourseHaystackViewSet):
    facet_serializer_class = serializers.CourseRunFacetSerializer
    index_models = (CourseRun,)
    serializer_class = serializers.CourseRunSearchSerializer


# TODO Remove the detail routes. They don't work, and make no sense here given that we cannot specify the type.
class AggregateSearchViewSet(BaseCourseHaystackViewSet):
    """ Search all content types. """
    facet_serializer_class = serializers.AggregateFacetSearchSerializer
    serializer_class = serializers.AggregateSearchSerializer
