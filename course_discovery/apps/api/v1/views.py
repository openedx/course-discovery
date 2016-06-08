import datetime
import logging
import os
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import transaction
from django.db.models import Q
from django.db.models.functions import Lower
from django.shortcuts import get_object_or_404
from dry_rest_permissions.generics import DRYPermissions
from edx_rest_framework_extensions.permissions import IsSuperuser
import pytz
from rest_framework import status, viewsets
from rest_framework.decorators import detail_route, list_route
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from course_discovery.apps.api.filters import PermissionsFilter
from course_discovery.apps.api.renderers import AffiliateWindowXMLRenderer
from course_discovery.apps.api.serializers import (
    CatalogSerializer, CourseSerializer, CourseRunSerializer, ContainedCoursesSerializer,
    CourseSerializerExcludingClosedRuns, AffiliateWindowSerializer, ContainedCourseRunsSerializer
)
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
    serializer_class = CatalogSerializer

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
        serializer: CourseSerializerExcludingClosedRuns
        """

        catalog = self.get_object()
        queryset = catalog.courses().active()

        page = self.paginate_queryset(queryset)
        serializer = CourseSerializerExcludingClosedRuns(page, many=True, context={'request': request})
        return self.get_paginated_response(serializer.data)

    @detail_route()
    def contains(self, request, id=None):  # pylint: disable=redefined-builtin,unused-argument
        """
        Determine if this catalog contains the provided courses.

        A dictionary mapping course IDs to booleans, indicating course presence, will be returned.
        ---
        serializer: ContainedCoursesSerializer
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
        serializer = ContainedCoursesSerializer(instance)
        return Response(serializer.data)


class CourseViewSet(viewsets.ReadOnlyModelViewSet):
    """ Course resource. """
    lookup_field = 'key'
    lookup_value_regex = COURSE_ID_REGEX
    queryset = Course.objects.all()
    permission_classes = (IsAuthenticated,)
    serializer_class = CourseSerializer

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
    serializer_class = CourseRunSerializer

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
        serializer: ContainedCourseRunsSerializer
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
            serializer = ContainedCourseRunsSerializer(instance)
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

        # Capture all output and logging
        out = StringIO()
        err = StringIO()
        log = StringIO()

        root_logger = logging.getLogger()
        log_handler = logging.StreamHandler(log)
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        log_handler.setFormatter(formatter)
        root_logger.addHandler(log_handler)

        logger.info('Updating course metadata per request of [%s]...', request.user.username)

        kwargs = {'access_token': access_token} if access_token else {}

        call_command('refresh_course_metadata', settings=os.environ['DJANGO_SETTINGS_MODULE'], stdout=out, stderr=err,
                     **kwargs)

        # Format the output for display
        output = 'STDOUT\n{out}\n\nSTDERR\n{err}\n\nLOG\n{log}'.format(out=out.getvalue(), err=err.getvalue(),
                                                                       log=log.getvalue())

        return Response(output, content_type='text/plain')


class AffiliateWindowViewSet(viewsets.ViewSet):
    """ AffiliateWindow Resource. """
    permission_classes = (IsAuthenticated,)
    renderer_classes = (AffiliateWindowXMLRenderer,)
    serializer_class = AffiliateWindowSerializer

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

        serializer = AffiliateWindowSerializer(seats, many=True)
        return Response(serializer.data)
