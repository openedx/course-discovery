import json

import ddt
from django.test import TestCase
from django.utils.encoding import force_text
from rest_framework.reverse import reverse

from course_discovery.apps.api.serializers import CatalogSerializer
from course_discovery.apps.catalogs.models import Catalog
from course_discovery.apps.catalogs.tests.factories import CatalogFactory
from course_discovery.apps.core.tests.factories import UserFactory, USER_PASSWORD

JSON = 'application/json'


@ddt.ddt
class CatalogViewSetTests(TestCase):
    """ Tests for the catalog resource.

    Read-only (GET) endpoints should NOT require authentication.
    """

    def setUp(self):
        super(CatalogViewSetTests, self).setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.catalog = CatalogFactory()

    def test_session_auth(self):
        # TODO Setup auth
        # TODO assert_create()
        # TODO assert_update()
        # TODO assert_update()
        pass

    def test_create_without_authentication(self):
        """ Verify authentication is required when creating, updating, or deleting a catalog. """
        self.client.logout()
        Catalog.objects.all().delete()

        response = self.client.post(reverse('api:v1:catalog-list'), data='{}', content_type=JSON)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Catalog.objects.count(), 0)

    @ddt.data('put', 'patch', 'delete')
    def test_modify_without_authentication(self, http_method):
        """ Verify authentication is required to modify a catalog. """
        self.client.logout()
        url = reverse('api:v1:catalog-detail', kwargs={'id': self.catalog.id})

        response = getattr(self.client, http_method)(url, data='{}', content_type=JSON)
        self.assertEqual(response.status_code, 403)

    def test_create(self):
        """ Verify the endpoint creates a new catalog. """
        name = 'The Kitchen Sink'
        query = '*.*'
        data = {
            'name': name,
            'query': query
        }

        response = self.client.post(reverse('api:v1:catalog-list'), data=json.dumps(data), content_type=JSON)
        self.assertEqual(response.status_code, 201)

        catalog = Catalog.objects.latest()
        self.assertDictEqual(response.data, CatalogSerializer(catalog).data)
        self.assertEqual(catalog.name, name)
        self.assertEqual(catalog.query, query)

    def test_courses(self):
        """ Verify the endpoint returns the list of courses contained in the catalog. """
        # TODO Use actual filtering!
        url = reverse('api:v1:catalog-courses', kwargs={'id': self.catalog.id})

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertListEqual(json.loads(force_text(response.content))['results'], [])

    def test_contains(self):
        """ Verify the endpoint returns a filtered list of courses contained in the catalog. """
        # TODO Use actual filtering!
        url = reverse('api:v1:catalog-contains', kwargs={'id': self.catalog.id}) + '?course_id=a,b,c'

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {'courses': {}})

    def test_get(self):
        """ Verify the endpoint returns the details for a single catalog. """
        url = reverse('api:v1:catalog-detail', kwargs={'id': self.catalog.id})

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, CatalogSerializer(self.catalog).data)

    def test_list(self):
        """ Verify the endpoint returns a list of all catalogs. """
        url = reverse('api:v1:catalog-list')

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertListEqual(response.data['results'], CatalogSerializer(Catalog.objects.all(), many=True).data)

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

        response = self.client.put(url, data=json.dumps(data), content_type=JSON)
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

        response = self.client.patch(url, data=json.dumps(data), content_type=JSON)
        self.assertEqual(response.status_code, 200)

        catalog = Catalog.objects.get(id=self.catalog.id)
        self.assertEqual(catalog.name, name)
        self.assertEqual(catalog.query, query)
