# pylint: disable=redefined-builtin

import json

import responses
from django.conf import settings
from rest_framework.test import APIRequestFactory

from course_discovery.apps.api.serializers import (
    CatalogSerializer, CourseSerializer, CourseSerializerExcludingClosedRuns
)


class SerializationMixin(object):
    def _get_request(self, format=None):
        query_data = {}
        if format:
            query_data['format'] = format
        request = APIRequestFactory().get('/', query_data)
        request.user = self.user
        return request

    def _serialize_object(self, serializer, obj, many=False, format=None):
        return serializer(obj, many=many, context={'request': self._get_request(format)}).data

    def serialize_catalog(self, catalog, many=False, format=None):
        return self._serialize_object(CatalogSerializer, catalog, many, format)

    def serialize_course(self, course, many=False, format=None):
        return self._serialize_object(CourseSerializer, course, many, format)

    def serialize_catalog_course(self, course, many=False, format=None):
        return self._serialize_object(CourseSerializerExcludingClosedRuns, course, many, format)


class OAuth2Mixin(object):
    def generate_oauth2_token_header(self, user):
        """ Generates a Bearer authorization header to simulate OAuth2 authentication. """
        return 'Bearer {token}'.format(token=user.username)

    def mock_user_info_response(self, user, status=200):
        """ Mock the user info endpoint response of the OAuth2 provider. """

        data = {
            'family_name': user.last_name,
            'preferred_username': user.username,
            'given_name': user.first_name,
            'email': user.email,
        }

        responses.add(
            responses.GET,
            settings.EDX_DRF_EXTENSIONS['OAUTH2_USER_INFO_URL'],
            body=json.dumps(data),
            content_type='application/json',
            status=status
        )
