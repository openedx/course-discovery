# pylint: disable=no-member
import urllib

import ddt
from django.db.models.functions import Lower
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase, APIRequestFactory

from course_discovery.apps.api.serializers import CourseRunSerializer
from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.core.tests.mixins import ElasticsearchTestMixin
from course_discovery.apps.course_metadata.models import CourseRun
from course_discovery.apps.course_metadata.tests.factories import CourseRunFactory, PartnerFactory


@ddt.ddt
class CourseRunViewSetTests(ElasticsearchTestMixin, APITestCase):
    def setUp(self):
        super(CourseRunViewSetTests, self).setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.client.force_authenticate(self.user)
        self.default_partner = PartnerFactory()
        self.course_run = CourseRunFactory(course__partner=self.default_partner)
        self.course_run_2 = CourseRunFactory(course__partner=self.default_partner)
        self.refresh_index()
        self.request = APIRequestFactory().get('/')
        self.request.user = self.user

    def serialize_course_run(self, course_run, **kwargs):
        return CourseRunSerializer(course_run, context={'request': self.request}, **kwargs).data

    def test_get(self):
        """ Verify the endpoint returns the details for a single course. """
        url = reverse('api:v1:course_run-detail', kwargs={'key': self.course_run.key})

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.serialize_course_run(self.course_run))

    def test_list(self):
        """ Verify the endpoint returns a list of all catalogs. """
        url = reverse('api:v1:course_run-list')

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertListEqual(
            response.data['results'],
            self.serialize_course_run(CourseRun.objects.all().order_by(Lower('key')), many=True)
        )

    def test_list_query(self):
        """ Verify the endpoint returns a filtered list of courses """
        course_runs = CourseRunFactory.create_batch(3, title='Some random title', course__partner=self.default_partner)
        CourseRunFactory(title='non-matching name')
        query = 'title:Some random title'
        url = '{root}?q={query}'.format(root=reverse('api:v1:course_run-list'), query=query)

        response = self.client.get(url)
        actual_sorted = sorted(response.data['results'], key=lambda course_run: course_run['key'])
        expected_sorted = sorted(self.serialize_course_run(course_runs, many=True),
                                 key=lambda course_run: course_run['key'])
        self.assertListEqual(actual_sorted, expected_sorted)

    def test_list_query_invalid_partner(self):
        """ Verify the endpoint returns an 400 BAD_REQUEST if an invalid partner is sent """
        query = 'title:Some random title'
        url = '{root}?q={query}&partner={partner}'.format(root=reverse('api:v1:course_run-list'), query=query,
                                                          partner='foo')

        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)

    def test_list_key_filter(self):
        """ Verify the endpoint returns a list of course runs filtered by the specified keys. """
        course_runs = CourseRunFactory.create_batch(3)
        course_runs = sorted(course_runs, key=lambda course: course.key.lower())
        keys = ','.join([course.key for course in course_runs])
        url = '{root}?keys={keys}'.format(root=reverse('api:v1:course_run-list'), keys=keys)

        response = self.client.get(url)
        self.assertListEqual(response.data['results'], self.serialize_course_run(course_runs, many=True))

    def test_contains_single_course_run(self):
        """ Verify that a single course_run is contained in a query """
        qs = urllib.parse.urlencode({
            'query': 'id:course*',
            'course_run_ids': self.course_run.key,
        })
        url = '{}?{}'.format(reverse('api:v1:course_run-contains'), qs)

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {
                'course_runs': {
                    self.course_run.key: True
                }
            }
        )

    def test_contains_single_course_run_invalid_partner(self):
        """ Verify that a 400 BAD_REQUEST is thrown when passing an invalid partner """
        qs = urllib.parse.urlencode({
            'query': 'id:course*',
            'course_run_ids': self.course_run.key,
            'partner': 'foo'
        })
        url = '{}?{}'.format(reverse('api:v1:course_run-contains'), qs)

        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)

    def test_contains_multiple_course_runs(self):
        qs = urllib.parse.urlencode({
            'query': 'id:course*',
            'course_run_ids': '{},{},{}'.format(self.course_run.key, self.course_run_2.key, 'abc')
        })
        url = '{}?{}'.format(reverse('api:v1:course_run-contains'), qs)

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertDictEqual(
            response.data,
            {
                'course_runs': {
                    self.course_run.key: True,
                    self.course_run_2.key: True,
                    'abc': False
                }
            }
        )

    @ddt.data(
        {'params': {'course_run_ids': 'a/b/c'}},
        {'params': {'query': 'id:course*'}},
        {'params': {}}
    )
    @ddt.unpack
    def test_contains_missing_parameter(self, params):
        qs = urllib.parse.urlencode(params)
        url = '{}?{}'.format(reverse('api:v1:course_run-contains'), qs)

        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)
