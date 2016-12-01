from rest_framework import viewsets
from rest_framework.filters import DjangoFilterBackend
from rest_framework.permissions import IsAuthenticated

from course_discovery.apps.api import filters, serializers


# pylint: disable=no-member
class OrganizationViewSet(viewsets.ReadOnlyModelViewSet):
    """ Organization resource. """

    filter_backends = (DjangoFilterBackend,)
    filter_class = filters.OrganizationFilter
    lookup_field = 'uuid'
    lookup_value_regex = '[0-9a-f-]+'
    permission_classes = (IsAuthenticated,)
    queryset = serializers.OrganizationSerializer.prefetch_queryset()
    serializer_class = serializers.OrganizationSerializer

    def list(self, request, *args, **kwargs):
        """ Retrieve a list of all organizations. """
        return super(OrganizationViewSet, self).list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """ Retrieve details for an organization. """
        return super(OrganizationViewSet, self).retrieve(request, *args, **kwargs)
