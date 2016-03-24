# pylint: disable=redefined-builtin
import datetime
import json
import urllib
from time import time
from unittest import skip

import ddt
import jwt
import responses
from django.conf import settings
from django.test import override_settings
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase, APIRequestFactory

from course_discovery.apps.api.serializers import CatalogSerializer, CourseSerializer
from course_discovery.apps.catalogs.models import Catalog
from course_discovery.apps.catalogs.tests.factories import CatalogFactory
from course_discovery.apps.core.tests.factories import UserFactory, USER_PASSWORD
from course_discovery.apps.core.tests.mixins import ElasticsearchTestMixin
from course_discovery.apps.course_metadata.tests.factories import CourseFactory

OAUTH2_ACCESS_TOKEN_URL = 'http://example.com/oauth2/access_token/'


class OAuth2Mixin(object):
    def get_access_token(self, user):
        """ Generates an OAuth2 access token for the user. """
        return user.username

    def generate_oauth2_token_header(self, user):
        """ Generates a Bearer authorization header to simulate OAuth2 authentication. """
        return 'Bearer {token}'.format(token=self.get_access_token(user))

    def mock_access_token_response(self, user, status=200):
        """ Mock the access token endpoint response of the OAuth2 provider. """
        url = '{root}/{token}'.format(root=OAUTH2_ACCESS_TOKEN_URL.rstrip('/'), token=self.get_access_token(user))
        expires = datetime.datetime.utcnow() + datetime.timedelta(days=1)

        responses.add(
            responses.GET,
            url,
            body=json.dumps({'username': user.username, 'scope': 'read', 'expires': expires.isoformat()}),
            content_type="application/json",
            status=status
        )


class SerializationMixin(object):
    def _get_request(self, format=None):
        query_data = {}
        if format:
            query_data['format'] = format
        return APIRequestFactory().get('/', query_data)

    def _serialize_object(self, serializer, obj, many=False, format=None):
        return serializer(obj, many=many, context={'request': self._get_request(format)}).data

    def serialize_catalog(self, catalog, many=False, format=None):
        return self._serialize_object(CatalogSerializer, catalog, many, format)

    def serialize_course(self, course, many=False, format=None):
        return self._serialize_object(CourseSerializer, course, many, format)


@ddt.ddt
@skip('Skip until ES search is resolved.')
class CatalogViewSetTests(ElasticsearchTestMixin, SerializationMixin, OAuth2Mixin, APITestCase):
    """ Tests for the catalog resource.

    Read-only (GET) endpoints should NOT require authentication.
    """

    def setUp(self):
        super(CatalogViewSetTests, self).setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        query = {
            'query': {
                'bool': {
                    'must': [
                        {
                            'wildcard': {
                                'course.name': 'abc*'
                            }
                        }
                    ]
                }
            }
        }
        self.catalog = CatalogFactory(query=json.dumps(query))
        self.course = CourseFactory(key='a/b/c', name='ABC Test Course')
        self.refresh_index()

    def generate_jwt_token_header(self, user):
        """Generate a valid JWT token header for authenticated requests."""
        now = int(time())
        ttl = 5
        payload = {
            'iss': settings.JWT_AUTH['JWT_ISSUER'],
            'aud': settings.JWT_AUTH['JWT_AUDIENCE'],
            'username': user.username,
            'email': user.email,
            'iat': now,
            'exp': now + ttl
        }

        token = jwt.encode(payload, settings.JWT_AUTH['JWT_SECRET_KEY']).decode('utf-8')

        return 'JWT {token}'.format(token=token)

    def test_create_without_authentication(self):
        """ Verify authentication is required when creating, updating, or deleting a catalog. """
        self.client.logout()
        Catalog.objects.all().delete()

        response = self.client.post(reverse('api:v1:catalog-list'), {}, format='json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Catalog.objects.count(), 0)

    @ddt.data('put', 'patch', 'delete')
    def test_modify_without_authentication(self, http_method):
        """ Verify authentication is required to modify a catalog. """
        self.client.logout()
        url = reverse('api:v1:catalog-detail', kwargs={'id': self.catalog.id})

        response = getattr(self.client, http_method)(url, {}, format='json')
        self.assertEqual(response.status_code, 403)

    def assert_catalog_created(self, **headers):
        name = 'The Kitchen Sink'
        query = '*.*'
        data = {
            'name': name,
            'query': query
        }

        response = self.client.post(reverse('api:v1:catalog-list'), data, format='json', **headers)
        self.assertEqual(response.status_code, 201)

        catalog = Catalog.objects.latest()
        self.assertDictEqual(response.data, self.serialize_catalog(catalog))
        self.assertEqual(catalog.name, name)
        self.assertEqual(catalog.query, query)

    def test_create_with_session_authentication(self):
        """ Verify the endpoint creates a new catalog when the client is authenticated via session authentication. """
        self.assert_catalog_created()

    def test_create_with_jwt_authentication(self):
        """ Verify the endpoint creates a new catalog when the client is authenticated via JWT authentication. """
        self.client.logout()
        self.assert_catalog_created(HTTP_AUTHORIZATION=self.generate_jwt_token_header(self.user))

    @responses.activate
    @override_settings(OAUTH2_ACCESS_TOKEN_URL=OAUTH2_ACCESS_TOKEN_URL)
    def test_create_with_oauth2_authentication(self):
        self.client.logout()
        self.mock_access_token_response(self.user)
        self.assert_catalog_created(HTTP_AUTHORIZATION=self.generate_oauth2_token_header(self.user))

    def test_courses(self):
        """ Verify the endpoint returns the list of courses contained in the catalog. """
        url = reverse('api:v1:catalog-courses', kwargs={'id': self.catalog.id})
        courses = [self.course]

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertListEqual(response.data['results'], self.serialize_course(courses, many=True))

    def test_contains(self):
        """ Verify the endpoint returns a filtered list of courses contained in the catalog. """
        course_key = self.course.key
        qs = urllib.parse.urlencode({'course_id': course_key})
        url = '{}?{}'.format(reverse('api:v1:catalog-contains', kwargs={'id': self.catalog.id}), qs)

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {'courses': {course_key: True}})

    def test_get(self):
        """ Verify the endpoint returns the details for a single catalog. """
        url = reverse('api:v1:catalog-detail', kwargs={'id': self.catalog.id})

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.serialize_catalog(self.catalog))

    def test_list(self):
        """ Verify the endpoint returns a list of all catalogs. """
        url = reverse('api:v1:catalog-list')

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertListEqual(response.data['results'], self.serialize_catalog(Catalog.objects.all(), many=True))

    def test_destroy(self):
        """ Verify the endpoint deletes a catalog. """
        url = reverse('api:v1:catalog-detail', kwargs={'id': self.catalog.id})

        response = self.client.delete(url)
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Catalog.objects.filter(id=self.catalog.id).exists())

    def test_update(self):
        """ Verify the endpoint updates a catalog. """
        url = reverse('api:v1:catalog-detail', kwargs={'id': self.catalog.id})
        name = 'Updated Catalog'
        query = 'so-not-real'

        data = {
            'name': name,
            'query': query
        }

        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, 200)

        catalog = Catalog.objects.get(id=self.catalog.id)
        self.assertEqual(catalog.name, name)
        self.assertEqual(catalog.query, query)

    def test_partial_update(self):
        """ Verify the endpoint supports partially updating a catalog's fields. """
        url = reverse('api:v1:catalog-detail', kwargs={'id': self.catalog.id})
        name = 'Updated Catalog'
        query = self.catalog.query
        data = {
            'name': name
        }

        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, 200)

        catalog = Catalog.objects.get(id=self.catalog.id)
        self.assertEqual(catalog.name, name)
        self.assertEqual(catalog.query, query)


@ddt.ddt
@skip('Skip until ES search is resolved.')
class CourseViewSetTests(ElasticsearchTestMixin, SerializationMixin, OAuth2Mixin, APITestCase):
    def setUp(self):
        super(CourseViewSetTests, self).setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.client.login(username=self.user.username, password=USER_PASSWORD)

    @ddt.data('json', 'api')
    def test_list(self, format):
        """ Verify the endpoint returns a list of all courses. """
        courses = CourseFactory.create_batch(10)
        courses.sort(key=lambda course: course.key.lower())
        url = reverse('api:v1:course-list')
        limit = 3
        self.refresh_index()

        response = self.client.get(url, {'format': format, 'limit': limit})
        self.assertEqual(response.status_code, 200)
        self.assertListEqual(response.data['results'], self.serialize_course(courses[:limit], many=True, format=format))

        response.render()

    def test_list_query(self):
        """ Verify the endpoint returns a filtered list of courses. """
        # Create courses that should NOT match our query
        CourseFactory.create_batch(3)

        # Create courses that SHOULD match our query
        name = 'query test'
        courses = [CourseFactory(name=name), CourseFactory(name=name)]
        courses.sort(key=lambda course: course.key.lower())
        self.refresh_index()

        query = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "term": {
                                "course.name": name
                            }
                        }
                    ]
                }
            }
        }
        qs = urllib.parse.urlencode({'q': json.dumps(query)})
        url = '{}?{}'.format(reverse('api:v1:course-list'), qs)

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], len(courses))
        self.assertListEqual(response.data['results'], self.serialize_course(courses, many=True))

    def test_retrieve(self):
        """ Verify the endpoint returns a single course. """
        self.assert_retrieve_success()

    def assert_retrieve_success(self, **headers):
        """ Asserts the endpoint returns details for a single course. """
        course = CourseFactory()
        url = reverse('api:v1:course-detail', kwargs={'id': course.key})
        response = self.client.get(url, format='json', **headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.serialize_course(course))

    @responses.activate
    @override_settings(OAUTH2_ACCESS_TOKEN_URL=OAUTH2_ACCESS_TOKEN_URL)
    def test_retrieve_with_oauth2_authentication(self):
        self.client.logout()
        self.mock_access_token_response(self.user)
        self.assert_retrieve_success(HTTP_AUTHORIZATION=self.generate_oauth2_token_header(self.user))
