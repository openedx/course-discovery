import logging

import waffle
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from course_discovery.apps.api import serializers
from course_discovery.apps.api.pagination import PageNumberPagination
from course_discovery.apps.api.v1.views import PartnerMixin

from course_discovery.apps.course_metadata.exceptions import MarketingSiteAPIClientException, PersonToMarketingException
from course_discovery.apps.course_metadata.people import MarketingSitePeople

logger = logging.getLogger(__name__)


# pylint: disable=no-member
class PersonViewSet(PartnerMixin, viewsets.ModelViewSet):
    """ PersonSerializer resource. """

    lookup_field = 'uuid'
    lookup_value_regex = '[0-9a-f-]+'
    permission_classes = (IsAuthenticated,)
    queryset = serializers.PersonSerializer.prefetch_queryset()
    serializer_class = serializers.PersonSerializer
    pagination_class = PageNumberPagination

    def create(self, request, *args, **kwargs):
        """ Create a new person. """
        person_data = request.data

        partner = self.get_partner()
        person_data['partner'] = partner.id
        serializer = self.get_serializer(data=person_data)
        serializer.is_valid(raise_exception=True)

        if waffle.switch_is_active('publish_person_to_marketing_site'):
            try:
                marketing_person = MarketingSitePeople()
                response = marketing_person.publish_person(
                    partner, {
                        'given_name': serializer.validated_data['given_name'],
                        'family_name': serializer.validated_data['family_name']
                    }
                )
                serializer.validated_data.pop('uuid')
                serializer.validated_data['uuid'] = response['uuid']

            except (PersonToMarketingException, MarketingSiteAPIClientException):
                logger.exception(
                    'An error occurred while adding the person [%s]-[%s] to the marketing site.',
                    serializer.validated_data['given_name'], serializer.validated_data['family_name']
                )
                return Response('Failed to add person data to the marketing site.', status=status.HTTP_400_BAD_REQUEST)

            try:
                self.perform_create(serializer)
            except Exception:  # pylint: disable=broad-except
                logger.exception(
                    'An error occurred while adding the person [%s]-[%s]-[%s].',
                    serializer.validated_data['given_name'], serializer.validated_data['family_name'],
                    response['id']
                )
                marketing_person.delete_person(partner, response['id'])
                return Response('Failed to add person data.', status=status.HTTP_400_BAD_REQUEST)

            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

        return Response('publish_program_to_marketing_site is disabled.', status=status.HTTP_400_BAD_REQUEST)

    def list(self, request, *args, **kwargs):
        """ Retrieve a list of all people. """
        return super(PersonViewSet, self).list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """ Retrieve details for a person. """
        return super(PersonViewSet, self).retrieve(request, *args, **kwargs)
