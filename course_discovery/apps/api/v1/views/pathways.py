""" Views for accessing Pathway data """
from course_discovery.apps.api import serializers
from course_discovery.apps.api.permissions import ReadOnlyByPublisherUser
from course_discovery.apps.course_metadata.models import Pathway
from rest_framework import viewsets
from rest_framework_extensions.cache.mixins import CacheResponseMixin


class PathwayViewSet(CacheResponseMixin, viewsets.ReadOnlyModelViewSet):
    permission_classes = (ReadOnlyByPublisherUser,)
    serializer_class = serializers.PathwaySerializer

    def get_queryset(self):
        return Pathway.objects.filter(partner=self.request.site.partner).order_by('created')
