"""
API Views for learner_pathway app.
"""
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
    queryset = models.LearnerPathway.objects.filter(status=PathwayStatus.Active)

    # Explicitly support PageNumberPagination and LimitOffsetPagination. Future
    # versions of this API should only support the system default, PageNumberPagination.
    pagination_class = ProxiedPagination


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
