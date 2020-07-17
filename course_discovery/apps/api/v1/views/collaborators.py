import logging

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.permissions import DjangoModelPermissionsOrAnonReadOnly
from rest_framework.response import Response

from course_discovery.apps.api import filters, serializers
from course_discovery.apps.api.cache import CompressedCacheResponseMixin
from course_discovery.apps.api.pagination import PageNumberPagination
from course_discovery.apps.api.serializers import MetadataWithRelatedChoices

logger = logging.getLogger(__name__)


# pylint: disable=useless-super-delegation
class CollaboratorViewSet(CompressedCacheResponseMixin, viewsets.ModelViewSet):
    """ CollaboratorSerializer resource. """

    permission_classes = (DjangoModelPermissionsOrAnonReadOnly,)
    queryset = serializers.CollaboratorSerializer.prefetch_queryset()
    serializer_class = serializers.CollaboratorSerializer
    pagination_class = PageNumberPagination
    metadata_class = MetadataWithRelatedChoices

    def create(self, request, *args, **kwargs):
        """
        Create a collaborator in discovery
        """

        collaborator_data = request.data
        serializer = self.get_serializer(data=collaborator_data)
        serializer.is_valid(raise_exception=True)

        try:
            self.perform_create(serializer)
        except Exception:  # pylint: disable=broad-except
            logger.exception(
                'An error occured while adding the collaborator [%s] in discovery.',
                serializer.validated_data['name'],
            )
            return Response('Failed to add collaborator data.', status=status.HTTP_400_BAD_REQUEST)

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update_collaborator(self, data, partial=False):
        """
        Updates a collaborator in discovery
        """

        collaborator_data = data
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=collaborator_data, partial=partial)
        serializer.is_valid(raise_exception=True)

        try:
            self.perform_update(serializer)
        except Exception:  # pylint: disable=broad-except
            logger.exception(
                'An error occured while updating the collaborator [%s]-[%s] in discovery.',
                serializer.validated_data['name'], serializer.validated_data['uuid']
            )
            return Response('Failed to update collaborator data.', status=status.HTTP_400_BAD_REQUEST)

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_200_OK, headers=headers)

    def update(self, request, *args, **kwargs):
        return self.update_collaborator(request.data)

    def partial_update(self, request, *_args, **_kwargs):
        """ Partially update details of collaborator. """
        return self.update_collaborator(request.data, partial=True)

    def list(self, request, *args, **kwargs):
        """ Retrieve a list of all collaborators. """
        return super(CollaboratorViewSet, self).list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """ Retieve details for a collaborator. """
        return super(CollaboratorViewSet, self).retrieve(request, *args, **kwargs)
