from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from course_discovery.apps.api import serializers
from course_discovery.apps.api.pagination import ProxiedPagination
from course_discovery.apps.api.renderers import AffiliateWindowXMLRenderer
from course_discovery.apps.api.utils import check_catalog_api_access
from course_discovery.apps.catalogs.models import Catalog
from course_discovery.apps.course_metadata.models import CourseRun, CourseType, ProgramType, Seat


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
        catalog_api_access_response = check_catalog_api_access(request.site.partner, request.user)
        # exclude 2u products if the requesting user has approval for accessing catalog api
        if catalog_api_access_response and catalog_api_access_response.get('status') == 'approved':
            course_types_2U = [CourseType.EXECUTIVE_EDUCATION_2U, CourseType.BOOTCAMP_2U]
            courses = courses.exclude(type__slug__in=course_types_2U)

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

        exclude_type_slugs = [
            ProgramType.MASTERS, ProgramType.BACHELORS, ProgramType.DOCTORATE,
            ProgramType.LICENSE, ProgramType.CERTIFICATE
        ]
        exclude_types = ProgramType.objects.filter(slug__in=exclude_type_slugs)

        programs = catalog.programs().marketable().exclude(type__in=exclude_types).select_related(
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
