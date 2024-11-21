"""
API Views for learner_pathway app.
"""
from django.db.models import Prefetch, Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from course_discovery.apps.api.pagination import ProxiedPagination
from course_discovery.apps.api.utils import get_excluded_restriction_types
from course_discovery.apps.course_metadata.choices import CourseRunStatus
from course_discovery.apps.course_metadata.models import CourseRun
from course_discovery.apps.learner_pathway import models
from course_discovery.apps.learner_pathway.api import serializers
from course_discovery.apps.learner_pathway.api.filters import PathwayUUIDFilter
from course_discovery.apps.learner_pathway.choices import PathwayStatus


class LearnerPathwayViewSet(ReadOnlyModelViewSet):
    """
    View-set for LearnerPathway model.
    """

    lookup_field = 'uuid'
    serializer_class = serializers.LearnerPathwaySerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = PathwayUUIDFilter

    # Explicitly support PageNumberPagination and LimitOffsetPagination. Future
    # versions of this API should only support the system default, PageNumberPagination.
    pagination_class = ProxiedPagination

    def get_queryset(self):
        excluded_restriction_types = get_excluded_restriction_types(self.request)
        course_runs = CourseRun.objects.filter(
            status=CourseRunStatus.Published
        ).exclude(
            restricted_run__restriction_type__in=excluded_restriction_types
        )

        return models.LearnerPathway.objects.filter(status=PathwayStatus.Active.value).prefetch_related(
            'steps',
            Prefetch('steps__learnerpathwaycourse_set__course__course_runs', queryset=course_runs),
            Prefetch('steps__learnerpathwayprogram_set__program__courses__course_runs', queryset=course_runs),
        )

    @action(detail=True)
    def snapshot(self, request, uuid):
        pathway = get_object_or_404(self.get_queryset(), uuid=uuid, status=PathwayStatus.Active.value)
        serializer = serializers.LearnerPathwaySerializer(pathway, many=False, context={'request': self.request})
        return Response(data=serializer.data, status=status.HTTP_200_OK)

    @action(detail=False)
    def uuids(self, request):
        """
        Return uuids of all pathways having course/courserun key or program uuid
        """
        course_keys = request.GET.getlist('course_keys', [])
        program_uuids = request.GET.getlist('program_uuids', [])
        query = Q(course__key__in=course_keys) | Q(course__course_runs__key__in=course_keys)
        pathway_courses = models.LearnerPathwayCourse.objects.filter(query).values_list(
            'step__pathway__uuid',
            flat=True
        )
        pathway_programs = models.LearnerPathwayProgram.objects.filter(
            program__uuid__in=program_uuids
        ).values_list(
            'step__pathway__uuid',
            flat=True
        )

        ids = list(pathway_courses) + list(pathway_programs)
        return Response(set(ids))


class LearnerPathwayStepViewSet(ReadOnlyModelViewSet):
    """
    View-set for LearnerPathwayStep model.
    """

    lookup_field = 'uuid'
    serializer_class = serializers.LearnerPathwayStepSerializer

    # Explicitly support PageNumberPagination and LimitOffsetPagination. Future
    # versions of this API should only support the system default, PageNumberPagination.
    pagination_class = ProxiedPagination

    def get_queryset(self):
        excluded_restriction_types = get_excluded_restriction_types(self.request)
        course_runs = CourseRun.objects.filter(
            status=CourseRunStatus.Published
        ).exclude(
            restricted_run__restriction_type__in=excluded_restriction_types
        )

        return models.LearnerPathwayStep.objects.prefetch_related(
            Prefetch('learnerpathwaycourse_set__course__course_runs', queryset=course_runs),
            Prefetch('learnerpathwayprogram_set__program__courses__course_runs', queryset=course_runs),
        )


class LearnerPathwayCourseViewSet(ReadOnlyModelViewSet):
    """
    View-set for LearnerPathwayCourse model.
    """

    lookup_field = 'uuid'
    serializer_class = serializers.LearnerPathwayCourseSerializer

    # Explicitly support PageNumberPagination and LimitOffsetPagination. Future
    # versions of this API should only support the system default, PageNumberPagination.
    pagination_class = ProxiedPagination

    def get_queryset(self):
        excluded_restriction_types = get_excluded_restriction_types(self.request)
        return models.LearnerPathwayCourse.objects.prefetch_related(
            Prefetch(
                'course__course_runs',
                queryset=CourseRun.objects.filter(status=CourseRunStatus.Published).exclude(
                    restricted_run__restriction_type__in=excluded_restriction_types
                ),
            )
        )


class LearnerPathwayProgramViewSet(ReadOnlyModelViewSet):
    """
    View-set for LearnerPathwayProgram model.
    """

    lookup_field = 'uuid'
    serializer_class = serializers.LearnerPathwayProgramSerializer

    # Explicitly support PageNumberPagination and LimitOffsetPagination. Future
    # versions of this API should only support the system default, PageNumberPagination.
    pagination_class = ProxiedPagination

    def get_queryset(self):
        excluded_restriction_types = get_excluded_restriction_types(self.request)
        return models.LearnerPathwayProgram.objects.prefetch_related(
            Prefetch(
                'program__courses__course_runs',
                queryset=CourseRun.objects.filter(status=CourseRunStatus.Published).exclude(
                    restricted_run__restriction_type__in=excluded_restriction_types
                ),
            )
        )


class LearnerPathwayBlocViewSet(ReadOnlyModelViewSet):
    """
    View-set for LearnerPathwayBlock model.
    """

    lookup_field = 'uuid'
    serializer_class = serializers.LearnerPathwayBlockSerializer
    queryset = models.LearnerPathwayBlock.objects.all()

    # Explicitly support PageNumberPagination and LimitOffsetPagination. Future
    # versions of this API should only support the system default, PageNumberPagination.
    pagination_class = ProxiedPagination
