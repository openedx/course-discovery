import logging

from django.db.models.functions import Lower
from rest_framework import viewsets
from rest_framework.decorators import detail_route
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from course_discovery.apps.api.serializers import CatalogSerializer, CourseSerializer, ContainedCoursesSerializer
from course_discovery.apps.catalogs.models import Catalog
from course_discovery.apps.course_metadata.constants import COURSE_ID_REGEX
from course_discovery.apps.course_metadata.models import Course

logger = logging.getLogger(__name__)


# pylint: disable=no-member
class CatalogViewSet(viewsets.ModelViewSet):
    """ Catalog resource. """

    lookup_field = 'id'
    queryset = Catalog.objects.all()
    serializer_class = CatalogSerializer

    def create(self, request, *args, **kwargs):
        """ Create a new catalog. """
        return super(CatalogViewSet, self).create(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """ Destroy a catalog. """
        return super(CatalogViewSet, self).destroy(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        """ Retrieve a list of all catalogs. """
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
        ---
        serializer: CourseSerializer
        """

        catalog = self.get_object()
        queryset = catalog.courses()

        page = self.paginate_queryset(queryset)
        serializer = CourseSerializer(page, many=True, context={'request': request})
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
    permission_classes = (IsAuthenticated,)
    serializer_class = CourseSerializer
    queryset = Course.objects.all().order_by(Lower('key'))

    def list(self, request, *args, **kwargs):
        """ List all courses. """
        return super(CourseViewSet, self).list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """ Retrieve details for a course. """
        return super(CourseViewSet, self).retrieve(request, *args, **kwargs)
