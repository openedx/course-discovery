# pylint: disable=redefined-builtin
import json
import urllib

import ddt
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase, APIRequestFactory

from course_discovery.apps.api.serializers import CatalogSerializer, CourseSerializer
from course_discovery.apps.catalogs.models import Catalog
from course_discovery.apps.catalogs.tests.factories import CatalogFactory
from course_discovery.apps.core.tests.factories import UserFactory, USER_PASSWORD
from course_discovery.apps.core.tests.mixins import ElasticsearchTestMixin
from course_discovery.apps.courses.tests.factories import CourseFactory


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
class CatalogViewSetTests(ElasticsearchTestMixin, SerializationMixin, APITestCase):
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
        self.course = CourseFactory(id='a/b/c', name='ABC Test Course')
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

    def test_create(self):
        """ Verify the endpoint creates a new catalog. """
        name = 'The Kitchen Sink'
        query = '*.*'
        data = {
            'name': name,
            'query': query
        }

        response = self.client.post(reverse('api:v1:catalog-list'), data, format='json')
        self.assertEqual(response.status_code, 201)

        catalog = Catalog.objects.latest()
        self.assertDictEqual(response.data, self.serialize_catalog(catalog))
        self.assertEqual(catalog.name, name)
        self.assertEqual(catalog.query, query)

    def test_courses(self):
        """ Verify the endpoint returns the list of courses contained in the catalog. """
        url = reverse('api:v1:catalog-courses', kwargs={'id': self.catalog.id})
        courses = [self.course]

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertListEqual(response.data['results'], self.serialize_course(courses, many=True))

    def test_contains(self):
        """ Verify the endpoint returns a filtered list of courses contained in the catalog. """
        course_id = self.course.id
        qs = urllib.parse.urlencode({'course_id': course_id})
        url = '{}?{}'.format(reverse('api:v1:catalog-contains', kwargs={'id': self.catalog.id}), qs)

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {'courses': {course_id: True}})

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
        """ Verify the endpoint supports partially updating a catlaog's fields. """
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
class CourseViewSetTests(ElasticsearchTestMixin, SerializationMixin, APITestCase):
    def setUp(self):
        super(CourseViewSetTests, self).setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.client.login(username=self.user.username, password=USER_PASSWORD)

    @ddt.data('json', 'api')
    def test_list(self, format):
        """ Verify the endpoint returns a list of all courses. """
        courses = CourseFactory.create_batch(10)
        courses.sort(key=lambda course: course.id.lower())
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
        courses.sort(key=lambda course: course.id.lower())
        self.refresh_index()

        query = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "term": {
                                "course.name.lowercase_sort": name
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
        course = CourseFactory()
        url = reverse('api:v1:course-detail', kwargs={'id': course.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.serialize_course(course))
