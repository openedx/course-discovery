import json

from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from course_discovery.apps.api import serializers
from course_discovery.apps.api.pagination import PageNumberPagination
from course_discovery.apps.api.v1.views import PartnerMixin


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
        person_data = json.loads(request.data.get('data'))

        partner = self.get_partner()
        person_data['partner'] = partner.id

        serializer = self.get_serializer(data=person_data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def list(self, request, *args, **kwargs):
        """ Retrieve a list of all people. """
        return super(PersonViewSet, self).list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """ Retrieve details for a person. """
        return super(PersonViewSet, self).retrieve(request, *args, **kwargs)
