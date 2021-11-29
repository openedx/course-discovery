"""
API Views for learner_pathway app.
"""
from rest_framework import viewsets

from course_discovery.apps.api.pagination import ProxiedPagination
from course_discovery.apps.learner_pathway import models
from course_discovery.apps.learner_pathway.api import serializers


class LearnerPathwayViewSet(viewsets.ModelViewSet):
    """
    View-set for LearnerPathway model.
    """

    lookup_field = 'uuid'
    serializer_class = serializers.LearnerPathwaySerializer
    queryset = models.LearnerPathway.objects.all()

    # Explicitly support PageNumberPagination and LimitOffsetPagination. Future
    # versions of this API should only support the system default, PageNumberPagination.
    pagination_class = ProxiedPagination


class LearnerPathwayStepViewSet(viewsets.ModelViewSet):
    """
    View-set for LearnerPathwayStep model.
    """

    lookup_field = 'uuid'
    serializer_class = serializers.LearnerPathwayStepSerializer
    queryset = models.LearnerPathwayStep.objects.all()

    # Explicitly support PageNumberPagination and LimitOffsetPagination. Future
    # versions of this API should only support the system default, PageNumberPagination.
    pagination_class = ProxiedPagination


class LearnerPathwayCourseViewSet(viewsets.ModelViewSet):
    """
    View-set for LearnerPathwayCourse model.
    """

    lookup_field = 'uuid'
    serializer_class = serializers.LearnerPathwayCourseSerializer
    queryset = models.LearnerPathwayCourse.objects.all()

    # Explicitly support PageNumberPagination and LimitOffsetPagination. Future
    # versions of this API should only support the system default, PageNumberPagination.
    pagination_class = ProxiedPagination


class LearnerPathwayProgramViewSet(viewsets.ModelViewSet):
    """
    View-set for LearnerPathwayProgram model.
    """

    lookup_field = 'uuid'
    serializer_class = serializers.LearnerPathwayProgramSerializer
    queryset = models.LearnerPathwayProgram.objects.all()

    # Explicitly support PageNumberPagination and LimitOffsetPagination. Future
    # versions of this API should only support the system default, PageNumberPagination.
    pagination_class = ProxiedPagination
