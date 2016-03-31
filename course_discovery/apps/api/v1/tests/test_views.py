# pylint: disable=redefined-builtin
import json
import urllib

import ddt
import responses
from django.conf import settings
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase, APIRequestFactory

from course_discovery.apps.api.serializers import CatalogSerializer, CourseSerializer
from course_discovery.apps.api.tests.jwt_utils import generate_jwt_header_for_user
from course_discovery.apps.catalogs.models import Catalog
from course_discovery.apps.catalogs.tests.factories import CatalogFactory
from course_discovery.apps.core.tests.factories import UserFactory, USER_PASSWORD
from course_discovery.apps.core.tests.mixins import ElasticsearchTestMixin
from course_discovery.apps.course_metadata.tests.factories import CourseFactory
from course_discovery.apps.course_metadata.models import Course


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
class CatalogViewSetTests(ElasticsearchTestMixin, SerializationMixin, OAuth2Mixin, APITestCase):
    """ Tests for the catalog resource.

    Read-only (GET) endpoints should NOT require authentication.
    """

    def setUp(self):
        super(CatalogViewSetTests, self).setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.catalog = CatalogFactory(query='title:abc*')
        self.course = CourseFactory(key='a/b/c', title='ABC Test Course')
        self.refresh_index()

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
        self.assert_catalog_created(HTTP_AUTHORIZATION=generate_jwt_header_for_user(self.user))

    @responses.activate
    def test_create_with_oauth2_authentication(self):
        self.client.logout()
        self.mock_user_info_response(self.user)
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


class CourseViewSetTests(SerializationMixin, OAuth2Mixin, APITestCase):
    def setUp(self):
        super(CourseViewSetTests, self).setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.course = CourseFactory()

    def test_get(self):
        """ Verify the endpoint returns the details for a single course. """
        url = reverse('api:v1:course-detail', kwargs={'key': self.course.key})

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.serialize_course(self.course))

    def test_list(self):
        """ Verify the endpoint returns a list of all catalogs. """
        url = reverse('api:v1:course-list')

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertListEqual(response.data['results'], self.serialize_course(Course.objects.all(), many=True))
