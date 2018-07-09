""" Views for accessing CreditPathway data """
from rest_framework import viewsets
from rest_framework_extensions.cache.mixins import CacheResponseMixin

from course_discovery.apps.api import serializers
from course_discovery.apps.api.permissions import ReadOnlyByPublisherUser

from course_discovery.apps.course_metadata.models import CreditPathway


class CreditPathwayViewSet(CacheResponseMixin, viewsets.ReadOnlyModelViewSet):
    permission_classes = (ReadOnlyByPublisherUser,)
    serializer_class = serializers.CreditPathwaySerializer
    queryset = CreditPathway.objects.all()
