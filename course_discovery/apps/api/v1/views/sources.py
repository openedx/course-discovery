from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from course_discovery.apps.api import serializers
from course_discovery.apps.api.cache import CompressedCacheResponseMixin
from course_discovery.apps.api.permissions import IsCourseRunEditorOrDjangoOrReadOnly
from course_discovery.apps.course_metadata.models import Source


class SourceViewSet(CompressedCacheResponseMixin, viewsets.ReadOnlyModelViewSet):
    """ Source resource. """

    permission_classes = (IsAuthenticated, IsCourseRunEditorOrDjangoOrReadOnly)
    serializer_class = serializers.SourceSerializer
    lookup_field = 'slug'
    queryset = Source.objects.all()
