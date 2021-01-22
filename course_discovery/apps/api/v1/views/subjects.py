from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from course_discovery.apps.api import filters, serializers
from course_discovery.apps.api.pagination import ProxiedPagination


# pylint: disable=useless-super-delegation
class SubjectViewSet(viewsets.ReadOnlyModelViewSet):
    """ Subject resource. """

    filter_backends = (DjangoFilterBackend,)
    filterset_class = filters.SubjectFilter
    lookup_field = 'uuid'
    lookup_value_regex = '[0-9a-f-]+'
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.SubjectSerializer

    # Explicitly support PageNumberPagination and LimitOffsetPagination. Future
    # versions of this API should only support the system default, PageNumberPagination.
    pagination_class = ProxiedPagination

    def get_queryset(self):
        return serializers.SubjectSerializer.prefetch_queryset()

    def list(self, request, *args, **kwargs):
        """ Retrieve a list of all subjects. """
        return super().list(request, *args, **kwargs)  # pylint: disable=no-member

    def retrieve(self, request, *args, **kwargs):
        """ Retrieve details for an subject. """
        return super().retrieve(request, *args, **kwargs)
