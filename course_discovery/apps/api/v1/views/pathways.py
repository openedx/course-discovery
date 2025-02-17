""" Views for accessing Pathway data """
from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend

from course_discovery.apps.api import serializers
from course_discovery.apps.api.cache import CompressedCacheResponseMixin
from course_discovery.apps.api.permissions import ReadOnlyByPublisherUser
from course_discovery.apps.api.utils import get_excluded_restriction_types
from course_discovery.apps.course_metadata.models import CourseRun


class PathwayViewSet(CompressedCacheResponseMixin, viewsets.ReadOnlyModelViewSet):
    permission_classes = (ReadOnlyByPublisherUser,)
    serializer_class = serializers.PathwaySerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_fields = ('status',)

    def get_queryset(self):
        excluded_restriction_types = get_excluded_restriction_types(self.request)
        course_runs = CourseRun.objects.exclude(restricted_run__restriction_type__in=excluded_restriction_types)

        queryset = self.get_serializer_class().prefetch_queryset(
            partner=self.request.site.partner,
            course_runs=course_runs
        )
        return queryset.order_by('created')
