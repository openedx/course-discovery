"""
API Views for learner_pathway app.
"""

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from course_discovery.apps.api.pagination import ProxiedPagination
from course_discovery.apps.learner_pathway import models
from course_discovery.apps.learner_pathway.api import serializers
from course_discovery.apps.learner_pathway.choices import PathwayStatus


class LearnerPathwayViewSet(ReadOnlyModelViewSet):
    """
    View-set for LearnerPathway model.
    """

    lookup_field = 'uuid'
    serializer_class = serializers.LearnerPathwaySerializer
    queryset = models.LearnerPathway.objects.prefetch_related('steps').filter(status=PathwayStatus.Active)

    # Explicitly support PageNumberPagination and LimitOffsetPagination. Future
    # versions of this API should only support the system default, PageNumberPagination.
    pagination_class = ProxiedPagination

    @action(detail=True)
    def snapshot(self, request, uuid):
        pathway = get_object_or_404(self.queryset, uuid=uuid, status=PathwayStatus.Active)
        serializer = serializers.LearnerPathwayMinimalSerializer(pathway, many=False)
        return Response(data=serializer.data, status=status.HTTP_200_OK)


class LearnerPathwayStepViewSet(ReadOnlyModelViewSet):
    """
    View-set for LearnerPathwayStep model.
    """

    lookup_field = 'uuid'
    serializer_class = serializers.LearnerPathwayStepSerializer
    queryset = models.LearnerPathwayStep.objects.all()

    # Explicitly support PageNumberPagination and LimitOffsetPagination. Future
    # versions of this API should only support the system default, PageNumberPagination.
    pagination_class = ProxiedPagination


class LearnerPathwayCourseViewSet(ReadOnlyModelViewSet):
    """
    View-set for LearnerPathwayCourse model.
    """

    lookup_field = 'uuid'
    serializer_class = serializers.LearnerPathwayCourseSerializer
    queryset = models.LearnerPathwayCourse.objects.all()

    # Explicitly support PageNumberPagination and LimitOffsetPagination. Future
    # versions of this API should only support the system default, PageNumberPagination.
    pagination_class = ProxiedPagination


class LearnerPathwayProgramViewSet(ReadOnlyModelViewSet):
    """
    View-set for LearnerPathwayProgram model.
    """

    lookup_field = 'uuid'
    serializer_class = serializers.LearnerPathwayProgramSerializer
    queryset = models.LearnerPathwayProgram.objects.all()

    # Explicitly support PageNumberPagination and LimitOffsetPagination. Future
    # versions of this API should only support the system default, PageNumberPagination.
    pagination_class = ProxiedPagination


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
