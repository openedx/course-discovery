# pylint: disable=redefined-builtin

import json

import responses
from django.conf import settings
from rest_framework.test import APIRequestFactory

from course_discovery.apps.api.serializers import (
    CatalogCourseSerializer, CatalogSerializer, CourseRunWithProgramsSerializer,
    CourseWithProgramsSerializer, FlattenedCourseRunWithCourseSerializer, MinimalProgramSerializer,
    OrganizationSerializer, PersonSerializer, ProgramSerializer, ProgramTypeSerializer
)


class SerializationMixin(object):
    def _get_request(self, format=None):
        if getattr(self, 'request', None):
            return self.request

        query_data = {}
        if format:
            query_data['format'] = format
        request = APIRequestFactory().get('/', query_data)
        request.user = self.user
        return request

    def _serialize_object(self, serializer, obj, many=False, format=None, extra_context=None):
        context = {'request': self._get_request(format)}
        if extra_context:
            context.update(extra_context)

        return serializer(obj, many=many, context=context).data

    def serialize_catalog(self, catalog, many=False, format=None, extra_context=None):
        return self._serialize_object(CatalogSerializer, catalog, many, format, extra_context)

    def serialize_course(self, course, many=False, format=None, extra_context=None):
        return self._serialize_object(CourseWithProgramsSerializer, course, many, format, extra_context)

    def serialize_course_run(self, run, many=False, format=None, extra_context=None):
        return self._serialize_object(CourseRunWithProgramsSerializer, run, many, format, extra_context)

    def serialize_person(self, person, many=False, format=None, extra_context=None):
        return self._serialize_object(PersonSerializer, person, many, format, extra_context)

    def serialize_program(self, program, many=False, format=None, extra_context=None):
        return self._serialize_object(
            MinimalProgramSerializer if many else ProgramSerializer,
            program,
            many,
            format,
            extra_context
        )

    def serialize_program_type(self, program_type, many=False, format=None, extra_context=None):
        return self._serialize_object(ProgramTypeSerializer, program_type, many, format, extra_context)

    def serialize_catalog_course(self, course, many=False, format=None, extra_context=None):
        return self._serialize_object(CatalogCourseSerializer, course, many, format, extra_context)

    def serialize_catalog_flat_course_run(self, course_run, many=False, format=None, extra_context=None):
        return self._serialize_object(FlattenedCourseRunWithCourseSerializer, course_run, many, format, extra_context)

    def serialize_organization(self, organization, many=False, format=None, extra_context=None):
        return self._serialize_object(OrganizationSerializer, organization, many, format, extra_context)


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
