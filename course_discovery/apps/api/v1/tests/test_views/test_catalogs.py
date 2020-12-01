import csv
import datetime
import urllib
from io import StringIO

import ddt
import pytest
import pytz
from django.contrib.auth import get_user_model
from rest_framework.reverse import reverse

from course_discovery.apps.api.tests.jwt_utils import generate_jwt_header_for_user
from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase, OAuth2Mixin, SerializationMixin
from course_discovery.apps.catalogs.models import Catalog
from course_discovery.apps.catalogs.tests.factories import CatalogFactory
from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.core.tests.mixins import ElasticsearchTestMixin
from course_discovery.apps.course_metadata.models import Course
from course_discovery.apps.course_metadata.tests.factories import CourseRunFactory, SeatFactory, SeatTypeFactory
from course_discovery.conftest import get_course_run_states

User = get_user_model()

STATES, AVAILABLE_STATES = get_course_run_states()


@ddt.ddt
@pytest.mark.usefixtures('course_run_states')
class CatalogViewSetTests(ElasticsearchTestMixin, SerializationMixin, OAuth2Mixin, APITestCase):
    """ Tests for the catalog resource. """
    catalog_list_url = reverse('api:v1:catalog-list')

    def setUp(self):
        super().setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.request.user = self.user
        self.client.force_authenticate(self.user)
        self.catalog = CatalogFactory(query='title:abc*')
        enrollment_end = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=30)
        course_end = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=60)
        self.course_run = CourseRunFactory(
            enrollment_end=enrollment_end,
            end=course_end,
            course__title='ABC Test Course'
        )
        self.course = self.course_run.course
        self.refresh_index()

    def assert_catalog_created(self, **headers):
        name = 'The Kitchen Sink'
        query = '*.*'
        viewer = UserFactory()
        data = {
            'name': name,
            'query': query,
            'viewers': [viewer.username]
        }

        response = self.client.post(self.catalog_list_url, data, format='json', **headers)
        self.assertEqual(response.status_code, 201)

        catalog = Catalog.objects.latest()
        self.assertDictEqual(response.data, self.serialize_catalog(catalog))
        self.assertEqual(catalog.name, name)
        self.assertEqual(catalog.query, query)
        self.assertListEqual(list(catalog.viewers), [viewer])

    def assert_catalog_contains_query_string(self, query_string_kwargs, course_key):
        """
        Helper method to validate the provided course key or course run key
        in the catalog contains endpoint.
        """
        query_string = urllib.parse.urlencode(query_string_kwargs)
        url = '{base_url}?{query_string}'.format(
            base_url=reverse('api:v1:catalog-contains', kwargs={'id': self.catalog.id}),
            query_string=query_string
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {'courses': {course_key: True}})

    def grant_catalog_permission_to_user(self, user, action, catalog=None):
        """ Grant the user access to view `self.catalog`. """
        catalog = catalog or self.catalog
        perm = f'{action}_catalog'
        user.add_obj_perm(perm, catalog)
        self.assertTrue(user.has_perm('catalogs.' + perm, catalog))

    def test_create_without_authentication(self):
        """ Verify authentication is required when creating, updating, or deleting a catalog. """
        self.client.logout()
        Catalog.objects.all().delete()

        response = self.client.post(self.catalog_list_url, {}, format='json')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(Catalog.objects.count(), 0)

    @ddt.data('put', 'patch', 'delete')
    def test_modify_without_authentication(self, http_method):
        """ Verify authentication is required to modify a catalog. """
        self.client.logout()
        url = reverse('api:v1:catalog-detail', kwargs={'id': self.catalog.id})

        response = getattr(self.client, http_method)(url, {}, format='json')
        self.assertEqual(response.status_code, 401)

    def test_create_with_session_authentication(self):
        """ Verify the endpoint creates a new catalog when the client is authenticated via session authentication. """
        self.assert_catalog_created()

    def test_create_with_jwt_authentication(self):
        """ Verify the endpoint creates a new catalog when the client is authenticated via JWT authentication. """
        self.client.logout()
        self.assert_catalog_created(HTTP_AUTHORIZATION=generate_jwt_header_for_user(self.user))

    def test_create_with_new_user(self):
        """ Verify that new users are created if the list of viewers includes the usernames of non-existent users. """
        new_viewer_username = 'new-guy'
        existing_viewer = UserFactory()
        viewers = [new_viewer_username, existing_viewer.username]
        data = {
            'name': 'Test Catalog',
            'query': '*:*',
            'viewers': ','.join(viewers)
        }

        # NOTE: We explicitly avoid using the JSON data type so that we properly test string parsing.
        response = self.client.post(self.catalog_list_url, data)
        self.assertEqual(response.status_code, 201)

        catalog = Catalog.objects.latest()
        latest_user = User.objects.latest()
        assert latest_user.username == new_viewer_username
        assert set(catalog.viewers) == {existing_viewer, latest_user}

    def test_create_with_new_user_error(self):
        """ Verify no users are created if an error occurs while processing a create request. """
        # The missing name and query fields should trigger an error
        data = {
            'viewers': ['new-guy']
        }
        original_user_count = User.objects.count()
        response = self.client.post(self.catalog_list_url, data)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(User.objects.count(), original_user_count)

    @ddt.data(
        *STATES()
    )
    def test_courses(self, state):
        """
        Verify the endpoint returns the list of available courses contained in
        the catalog, and that courses appearing in the response always have at
        least one serialized run.
        """
        url = reverse('api:v1:catalog-courses', kwargs={'id': self.catalog.id})

        Course.objects.all().delete()

        course_run = CourseRunFactory(course__title='ABC Test Course')
        for function in state:
            function(course_run)

        course_run.save()

        if state in AVAILABLE_STATES:
            course = course_run.course

            # This run has no seats, but we still expect its parent course
            # to be included.
            filtered_course_run = CourseRunFactory(course=course)

            with self.assertNumQueries(31, threshold=3):
                response = self.client.get(url)

            assert response.status_code == 200

            # Emulate prefetching behavior.
            filtered_course_run.delete()

            assert response.data['results'] == self.serialize_catalog_course([course], many=True)

            # Any course appearing in the response must have at least one serialized run.
            assert response.data['results'][0]['course_runs']
        else:
            response = self.client.get(url)

            assert response.status_code == 200
            assert response.data['results'] == []

    def test_courses_with_include_archived(self):
        """
        Verify the endpoint returns the list of available and archived courses if include archived
        is True in catalog.
        """
        url = reverse('api:v1:catalog-courses', kwargs={'id': self.catalog.id})
        Course.objects.all().delete()

        now = datetime.datetime.now(pytz.UTC)
        future = now + datetime.timedelta(days=30)
        past = now - datetime.timedelta(days=30)

        course_run = CourseRunFactory.create(
            course__title='ABC Test Course With Archived', end=future, enrollment_end=future
        )
        SeatFactory.create(course_run=course_run)
        # Create an archived course run
        CourseRunFactory.create(course=course_run.course, end=past)

        response = self.client.get(url)

        assert response.status_code == 200
        # The course appearing in response should have on 1 course run
        assert len(response.data['results'][0]['course_runs']) == 1

        # Mark include archived True in catalog
        self.catalog.include_archived = True
        self.catalog.save()
        response = self.client.get(url)

        assert response.status_code == 200
        # The course appearing in response should include archived course run
        assert len(response.data['results'][0]['course_runs']) == 2

    def test_contains_for_course_key(self):
        """
        Verify the endpoint returns a filtered list of courses contained in
        the catalog for course keys with the format "org+course".
        """
        course_key = self.course.key
        query_string_kwargs = {'course_id': course_key}
        self.assert_catalog_contains_query_string(query_string_kwargs, course_key)

    def test_contains_for_course_run_key(self):
        """
        Verify the endpoint returns a filtered list of courses contained in
        the catalog for course run keys with the format "org/course/run" or
        "course-v1:org+course+key".
        """
        course_run_key = self.course_run.key
        query_string_kwargs = {'course_run_id': course_run_key}
        self.assert_catalog_contains_query_string(query_string_kwargs, course_run_key)

    def test_csv(self):
        SeatFactory(type=SeatTypeFactory.audit(), course_run=self.course_run)
        SeatFactory(type=SeatTypeFactory.verified(), course_run=self.course_run)
        SeatFactory(type=SeatTypeFactory.credit(), course_run=self.course_run, credit_provider='ASU', credit_hours=9)
        SeatFactory(type=SeatTypeFactory.credit(), course_run=self.course_run, credit_provider='Hogwarts',
                    credit_hours=4)

        url = reverse('api:v1:catalog-csv', kwargs={'id': self.catalog.id})

        with self.assertNumQueries(23):
            response = self.client.get(url)

        course_run = self.serialize_catalog_flat_course_run(self.course_run)
        expected = [
            course_run['announcement'],
            course_run['content_language'],
            course_run['course_key'],
            course_run['end'],
            course_run['enrollment_end'],
            course_run['enrollment_start'],
            course_run['expected_learning_items'],
            course_run['full_description'],
            '',  # image description
            '',  # image height
            course_run['image']['src'],
            '',  # image width
            course_run['key'],
            str(course_run['level_type']),
            course_run['marketing_url'],
            str(course_run['max_effort']),
            str(course_run['min_effort']),
            course_run['modified'],
            course_run['owners'],
            course_run['pacing_type'],
            course_run['prerequisites'],
            course_run['seats']['audit']['type'],
            '{}'.format(course_run['seats']['credit']['credit_hours']),
            '{}'.format(course_run['seats']['credit']['credit_provider']),
            '{}'.format(course_run['seats']['credit']['currency']),
            '{}'.format(str(course_run['seats']['credit']['price'])),
            '{}'.format(course_run['seats']['credit']['type']),
            '{}'.format(course_run['seats']['credit']['upgrade_deadline']),
            course_run['seats']['honor']['type'],
            course_run['seats']['masters']['type'],
            course_run['seats']['professional']['currency'],
            str(course_run['seats']['professional']['price']),
            course_run['seats']['professional']['type'],
            course_run['seats']['professional']['upgrade_deadline'],
            course_run['seats']['verified']['currency'],
            str(course_run['seats']['verified']['price']),
            course_run['seats']['verified']['type'],
            course_run['seats']['verified']['upgrade_deadline'],
            course_run['short_description'],
            course_run['sponsors'],
            course_run['start'],
            course_run['subjects'],
            course_run['title'],
            course_run['video']['description'],
            course_run['video']['image']['description'],
            str(course_run['video']['image']['height']),
            course_run['video']['image']['src'],
            str(course_run['video']['image']['width']),
            course_run['video']['src'],
        ]

        # collect streamed content
        received_content = b''
        for item in response.streaming_content:
            received_content += item

        # convert received content to csv for comparison
        f = StringIO(received_content.decode('utf-8'))
        reader = csv.reader(f)
        content = list(reader)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(expected, content[1])

    def test_get(self):
        """ Verify the endpoint returns the details for a single catalog. """
        url = reverse('api:v1:catalog-detail', kwargs={'id': self.catalog.id})

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.serialize_catalog(self.catalog))

    def test_list(self):
        """ Verify the endpoint returns a list of all catalogs. """
        response = self.client.get(self.catalog_list_url)
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

    def test_retrieve_permissions(self):
        """ Verify only users with the correct permissions can create, read, or modify a Catalog. """
        # Use an unprivileged user
        user = UserFactory(is_staff=False, is_superuser=False)
        self.client.force_authenticate(user)
        url = reverse('api:v1:catalog-detail', kwargs={'id': self.catalog.id})

        # A user with no permissions should NOT be able to view a Catalog.
        self.assertFalse(user.has_perm('catalogs.view_catalog', self.catalog))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

        # The permitted user should be able to view the Catalog.
        self.grant_catalog_permission_to_user(user, 'view')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_list_permissions(self):
        """ Verify only catalogs accessible to the user are returned in the list view. """
        user = UserFactory(is_staff=False, is_superuser=False)
        self.client.force_authenticate(user)

        # An user with no permissions should not see any catalogs
        response = self.client.get(self.catalog_list_url)
        self.assertEqual(response.status_code, 200)
        self.assertListEqual(response.data['results'], [])

        # The client should be able to see permissions for which it has access
        self.grant_catalog_permission_to_user(user, 'view')
        response = self.client.get(self.catalog_list_url)
        self.assertEqual(response.status_code, 200)
        self.assertListEqual(response.data['results'], self.serialize_catalog([self.catalog], many=True))

    def test_write_permissions(self):
        """ Verify only authorized users can update or delete Catalogs. """
        url = reverse('api:v1:catalog-detail', kwargs={'id': self.catalog.id})
        user = UserFactory(is_staff=False, is_superuser=False)
        self.client.force_authenticate(user)

        # Unprivileged users cannot modify Catalogs
        response = self.client.put(url)
        self.assertEqual(response.status_code, 403)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 403)

        # With the right permissions, the user can perform the specified actions
        self.grant_catalog_permission_to_user(user, 'change')
        response = self.client.patch(url, {'query': '*:*'})
        self.assertEqual(response.status_code, 200)

        self.grant_catalog_permission_to_user(user, 'delete')
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 204)

    def test_username_filter_as_non_staff_user(self):
        """ Verify HTTP 403 is returned when a non-staff user attempts to filter the Catalog list by username. """
        user = UserFactory(is_staff=False, is_superuser=False)
        self.client.force_authenticate(user)

        response = self.client.get(self.catalog_list_url + '?username=jack')
        self.assertEqual(response.status_code, 403)
        expected = {'detail': 'Only staff users are permitted to filter by username. Remove the username parameter.'}
        self.assertDictEqual(response.data, expected)

    def test_username_filter_as_staff_user(self):
        """ Verify a list of Catalogs accessible by the given user is returned when filtering by username as a
        staff user. """
        user = UserFactory(is_staff=False, is_superuser=False)
        catalog = CatalogFactory()

        path = f'{self.catalog_list_url}?username={user.username}'
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertListEqual(response.data['results'], [])

        self.grant_catalog_permission_to_user(user, 'view', catalog)

        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertListEqual(response.data['results'], self.serialize_catalog([catalog], many=True))

    def test_username_filter_as_staff_user_with_invalid_username(self):
        """ Verify HTTP 404 is returned if the given username does not correspond to an actual user. """
        username = 'jack'
        path = f'{self.catalog_list_url}?username={username}'
        response = self.client.get(path)
        self.assertEqual(response.status_code, 404)
        expected = {'detail': f'No user with the username [{username}] exists.'}
        self.assertDictEqual(response.data, expected)
