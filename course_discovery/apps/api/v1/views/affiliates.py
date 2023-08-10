from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from course_discovery.apps.api import serializers
from course_discovery.apps.api.pagination import ProxiedPagination
from course_discovery.apps.api.renderers import AffiliateWindowXMLRenderer
from course_discovery.apps.catalogs.models import Catalog
from course_discovery.apps.course_metadata.models import CourseRun, ProgramType, Seat


class AffiliateWindowViewSet(viewsets.ViewSet):
    """ AffiliateWindow Resource. """
    permission_classes = (IsAuthenticated,)
    renderer_classes = (AffiliateWindowXMLRenderer,)
    serializer_class = serializers.AffiliateWindowSerializer

    # Explicitly support PageNumberPagination and LimitOffsetPagination. Future
    # versions of this API should only support the system default, PageNumberPagination.
    pagination_class = ProxiedPagination

    def retrieve(self, request, pk=None):
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
        seats = seats.select_related(
            'course_run',
            'course_run__language',
            'course_run__course',
            'course_run__course__level_type',
            'course_run__course__partner',
            'course_run__course__type',
            'course_run__type',
            'type',
        ).prefetch_related(
            'course_run__course__authoring_organizations',
            'course_run__course__subjects',
        )

        serializer = serializers.AffiliateWindowSerializer(seats, many=True)
        return Response(serializer.data)


class ProgramsAffiliateWindowViewSet(viewsets.ViewSet):
    permission_classes = (IsAuthenticated,)
    renderer_classes = (AffiliateWindowXMLRenderer,)
    serializer_class = serializers.ProgramsAffiliateWindowSerializer

    def retrieve(self, request, pk=None):
        catalog = get_object_or_404(Catalog, pk=pk)

        if not catalog.has_object_read_permission(request):
            raise PermissionDenied

        try:
            exclude_type = ProgramType.objects.get(slug=ProgramType.MASTERS)
        except ProgramType.DoesNotExist:
            exclude_type = ''
        programs = catalog.programs().marketable().exclude(type=exclude_type).select_related(
            'type',
            'partner',
        ).prefetch_related(
            'excluded_course_runs',
            'type__applicable_seat_types',
            'type__translations',
            'courses',
            'courses__course_runs',
            'courses__course_runs__language',
            'courses__canonical_course_run',
            'courses__canonical_course_run__seats',
            'courses__canonical_course_run__seats__course_run__course',
            'courses__canonical_course_run__seats__type',
            'courses__canonical_course_run__seats__currency',
            'courses__course_runs__seats',
            'courses__entitlements',
            'courses__entitlements__currency',
            'courses__entitlements__mode',
        )
        serializer = serializers.ProgramsAffiliateWindowSerializer(programs, many=True)
        return Response(serializer.data)
