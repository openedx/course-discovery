import logging

from rest_framework import viewsets
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import IsAuthenticated

from course_discovery.apps.api import serializers
from course_discovery.apps.api.cache import CompressedCacheResponseMixin
from course_discovery.apps.api.pagination import PageNumberPagination
from course_discovery.apps.api.permissions import IsCourseEditorOrReadOnly

logger = logging.getLogger(__name__)


class CollaboratorViewSet(CompressedCacheResponseMixin, viewsets.ModelViewSet):
    """ CollaboratorSerializer resource. """

    lookup_field = 'uuid'
    lookup_value_regex = '[0-9a-f-]+'
    permission_classes = (IsAuthenticated, IsCourseEditorOrReadOnly,)
    queryset = serializers.CollaboratorSerializer.prefetch_queryset()
    serializer_class = serializers.CollaboratorSerializer
    pagination_class = PageNumberPagination
