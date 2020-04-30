from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated

from course_discovery.apps.api import filters, serializers
from course_discovery.apps.course_metadata.models import ProgramType


class ProgramTypeViewSet(viewsets.ReadOnlyModelViewSet):
    """ ProgramType resource. """
    lookup_field = 'slug'
    pagination_class = PageNumberPagination
    permission_classes = (IsAuthenticated,)
    queryset = serializers.ProgramTypeSerializer.prefetch_queryset(ProgramType.objects.all())
    serializer_class = serializers.ProgramTypeSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = filters.ProgramTypeFilter
