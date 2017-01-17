from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from course_discovery.apps.api import serializers
from course_discovery.apps.api.pagination import ProxiedPagination
from course_discovery.apps.api.renderers import AffiliateWindowXMLRenderer
from course_discovery.apps.catalogs.models import Catalog
from course_discovery.apps.course_metadata.models import CourseRun, Seat


class AffiliateWindowViewSet(viewsets.ViewSet):
    """ AffiliateWindow Resource. """
    permission_classes = (IsAuthenticated,)
    renderer_classes = (AffiliateWindowXMLRenderer,)
    serializer_class = serializers.AffiliateWindowSerializer

    # Explicitly support PageNumberPagination and LimitOffsetPagination. Future
    # versions of this API should only support the system default, PageNumberPagination.
    pagination_class = ProxiedPagination

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
