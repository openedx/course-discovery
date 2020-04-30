from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated

from course_discovery.apps.api import filters, serializers
from course_discovery.apps.course_metadata.models import LevelType


class LevelTypeViewSet(viewsets.ReadOnlyModelViewSet):
    """ LevelType resource. """
    lookup_field = 'translations__name_t'
    lookup_url_kwarg = 'name'
    pagination_class = PageNumberPagination
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.LevelTypeSerializer
    queryset = serializers.LevelTypeSerializer.prefetch_queryset(LevelType.objects.all())
    filter_backends = (DjangoFilterBackend,)
    filterset_class = filters.LevelTypeFilter
