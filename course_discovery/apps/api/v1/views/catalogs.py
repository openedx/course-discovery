import datetime

from django.db import transaction
from django.http import HttpResponse
from dry_rest_permissions.generics import DRYPermissions
from rest_framework import status, viewsets
from rest_framework.decorators import detail_route
from rest_framework.response import Response

from course_discovery.apps.api import filters, serializers
from course_discovery.apps.api.pagination import ProxiedPagination
from course_discovery.apps.api.renderers import CourseRunCSVRenderer
from course_discovery.apps.api.v1.views import User
from course_discovery.apps.catalogs.models import Catalog
from course_discovery.apps.course_metadata.models import CourseRun


# pylint: disable=no-member
class CatalogViewSet(viewsets.ModelViewSet):
    """ Catalog resource. """

    filter_backends = (filters.PermissionsFilter,)
    lookup_field = 'id'
    permission_classes = (DRYPermissions,)
    queryset = Catalog.objects.all()
    serializer_class = serializers.CatalogSerializer

    # Explicitly support PageNumberPagination and LimitOffsetPagination. Future
    # versions of this API should only support the system default, PageNumberPagination.
    pagination_class = ProxiedPagination

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

        Only courses with at least one course run that can be enrolled in immediately,
        is ongoing or yet to start, and appears on the marketing site are returned.
        ---
        serializer: serializers.CatalogCourseSerializer
        """
        catalog = self.get_object()
        queryset = catalog.courses().available()
        course_runs = CourseRun.objects.active().enrollable().marketable()

        queryset = serializers.CatalogCourseSerializer.prefetch_queryset(
            queryset=queryset,
            course_runs=course_runs
        )

        page = self.paginate_queryset(queryset)
        serializer = serializers.CatalogCourseSerializer(page, many=True, context={'request': request})
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
            - name: course_run_id
              description: Course run IDs to check for existence in the Catalog.
              required: false
              type: string
              paramType: query
              multiple: true
        """
        course_ids = request.query_params.get('course_id')
        course_run_ids = request.query_params.get('course_run_id')

        catalog = self.get_object()
        courses = {}
        if course_ids:
            course_ids = course_ids.split(',')
            courses.update(catalog.contains(course_ids))

        if course_run_ids:
            course_run_ids = course_run_ids.split(',')
            courses.update(catalog.contains_course_runs(course_run_ids))

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
