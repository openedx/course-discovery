import logging

from rest_framework import viewsets
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import IsAuthenticated

from course_discovery.apps.api import serializers
from course_discovery.apps.api.cache import CompressedCacheResponseMixin
from course_discovery.apps.api.permissions import IsInOrgOrReadOnly

logger = logging.getLogger(__name__)


# pylint: disable=useless-super-delegation
class CollaboratorViewSet(CompressedCacheResponseMixin, viewsets.ModelViewSet):
    """ CollaboratorSerializer resource. """

    lookup_field = 'uuid'
    lookup_value_regex = '[0-9a-f-]+'
    permission_classes = (IsAuthenticated, IsInOrgOrReadOnly,)
    queryset = serializers.CollaboratorSerializer.prefetch_queryset()
    serializer_class = serializers.CollaboratorSerializer
    pagination_class = CursorPagination

    def create(self, request, *args, **kwargs):
        logger.info('The raw collaborator data coming from the publisher POST is {}.'.format(request.data))

        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        logger.info('The raw collaborator data coming from the publisher PATCH is {}.'.format(request.data))

        return super().update(request, *args, **kwargs)  # pylint: disable=no-member

    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)  # pylint: disable=no-member

    def list(self, request, *args, **kwargs):
        """ Retrieve a list of all collaborators. """
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """ Retieve details for a collaborator. """
        return super().retrieve(request, *args, **kwargs)
