from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated

from course_discovery.apps.api import filters, serializers
from course_discovery.apps.course_metadata.models import LevelType


class LevelTypeViewSet(viewsets.ReadOnlyModelViewSet):
    """ ProgramType resource. """
    lookup_field = 'name'
    pagination_class = PageNumberPagination
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.LevelTypeSerializer

    filter_backends = (DjangoFilterBackend,)
    filterset_class = filters.LevelTypeFilter

    def get_queryset(self):
        return LevelType.objects.all()
