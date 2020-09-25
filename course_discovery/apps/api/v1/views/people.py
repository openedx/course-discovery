import logging

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.permissions import DjangoModelPermissionsOrAnonReadOnly
from rest_framework.response import Response

from course_discovery.apps.api import filters, serializers
from course_discovery.apps.api.cache import CompressedCacheResponseMixin
from course_discovery.apps.api.pagination import PageNumberPagination
from course_discovery.apps.api.serializers import MetadataWithRelatedChoices
from course_discovery.apps.course_metadata.exceptions import MarketingSiteAPIClientException, PersonToMarketingException

logger = logging.getLogger(__name__)


# pylint: disable=useless-super-delegation
class PersonViewSet(CompressedCacheResponseMixin, viewsets.ModelViewSet):
    """ PersonSerializer resource. """

    filter_backends = (DjangoFilterBackend,)
    filterset_class = filters.PersonFilter
    lookup_field = 'uuid'
    lookup_value_regex = '[0-9a-f-]+'
    permission_classes = (DjangoModelPermissionsOrAnonReadOnly,)
    queryset = serializers.PersonSerializer.prefetch_queryset()
    serializer_class = serializers.PersonSerializer
    pagination_class = PageNumberPagination
    metadata_class = MetadataWithRelatedChoices
    metadata_related_choices_whitelist = ('organization',)

    def create(self, request, *args, **kwargs):
        """
        Create a person in discovery and also create a person node in drupal
        """
        person_data = request.data
        person_data['published'] = True

        partner = request.site.partner
        person_data['partner'] = partner.id
        serializer = self.get_serializer(data=person_data)
        serializer.is_valid(raise_exception=True)

        try:
            self.perform_create(serializer)
        except (PersonToMarketingException, MarketingSiteAPIClientException):
            logger.exception(
                'An error occurred while adding the person [%s]-[%s] to the marketing site.',
                serializer.validated_data['given_name'], serializer.validated_data['family_name']
            )
            return Response('Failed to add person data to the marketing site.', status=status.HTTP_400_BAD_REQUEST)
        except Exception:  # pylint: disable=broad-except
            logger.exception(
                'An error occurred while adding the person [%s]-[%s] in discovery.',
                serializer.validated_data['given_name'], serializer.validated_data['family_name'],
            )
            return Response('Failed to add person data.', status=status.HTTP_400_BAD_REQUEST)

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        """
        Updates a person in discovery and the corresponding person node in drupal
        """
        person_data = request.data

        partner = request.site.partner
        person_data['partner'] = partner.id
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=person_data, partial=partial)
        serializer.is_valid(raise_exception=True)

        try:
            self.perform_update(serializer)
        except (PersonToMarketingException, MarketingSiteAPIClientException):
            logger.exception(
                'An error occurred while updating the person [%s]-[%s] on the marketing site.',
                serializer.validated_data['given_name'], serializer.validated_data['family_name']
            )
            return Response(
                'Failed to update person data on the marketing site.',
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception:  # pylint: disable=broad-except
            logger.exception(
                'An error occurred while updating the person [%s]-[%s] in discovery.',
                serializer.validated_data['given_name'], serializer.validated_data['family_name']
            )
            return Response('Failed to update person data.', status=status.HTTP_400_BAD_REQUEST)

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_200_OK, headers=headers)

    def list(self, request, *args, **kwargs):
        """ Retrieve a list of all people. """
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """ Retrieve details for a person. """
        return super().retrieve(request, *args, **kwargs)

    def get_queryset(self):
        # Only include people from the current request's site
        queryset = self.queryset.filter(partner=self.request.site.partner)
        org_keys = self.request.query_params.getlist('org', None)

        if org_keys:
            # We are pulling the people who are part of course runs belonging to the given organizations.
            # This blank order_by is there to offset the default ordering on people since
            # we don't care about the order in which they are returned.
            queryset = queryset.filter(courses_staffed__course__authoring_organizations__key__in=org_keys).order_by()

        return queryset
