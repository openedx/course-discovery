import urllib

from rest_framework.reverse import reverse

from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase
from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.course_metadata.tests.factories import CourseFactory, CourseRunFactory


class CatalogQueryViewSetTests(APITestCase):
    def setUp(self):
        super().setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.client.force_authenticate(self.user)
        self.course = CourseFactory(partner=self.partner, key='simple_key')
        self.course_run = CourseRunFactory(course=self.course)
        self.url_base = reverse('api:v1:catalog-query_contains')
        self.error_message = 'CatalogQueryContains endpoint requires query and identifiers list(s)'

    def test_contains_single_course_run(self):
        """ Verify that a single course_run is contained in a query. """
        qs = urllib.parse.urlencode({
            'query': 'id:' + self.course_run.key,
            'course_run_ids': self.course_run.key,
            'course_uuids': self.course.uuid,
        })
        url = f'{self.url_base}/?{qs}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {
                self.course_run.key: True,
                str(self.course.uuid): False
            }
        )

    def test_contains_single_course(self):
        """ Verify that a single course is contained in a query. """
        qs = urllib.parse.urlencode({
            'query': 'key:' + self.course.key,
            'course_run_ids': self.course_run.key,
            'course_uuids': self.course.uuid,
        })
        url = f'{self.url_base}/?{qs}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {
                self.course_run.key: False,
                str(self.course.uuid): True
            }
        )

    def test_contains_course_and_run(self):
        """ Verify that both the course and the run are contained in the broadest query. """
        self.course.course_runs.add(self.course_run)
        self.course.save()
        qs = urllib.parse.urlencode({
            'query': 'org:*',
            'course_run_ids': self.course_run.key,
            'course_uuids': self.course.uuid,
        })
        url = f'{self.url_base}/?{qs}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {
                self.course_run.key: True,
                str(self.course.uuid): True
            }
        )

    def test_no_identifiers(self):
        """ Verify that a 400 status is returned if request does not contain any identifier lists. """
        qs = urllib.parse.urlencode({
            'query': 'id:*'
        })
        url = f'{self.url_base}/?{qs}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, self.error_message)

    def test_no_query(self):
        """ Verify that a 400 status is returned if request does not contain a querystring. """
        qs = urllib.parse.urlencode({
            'course_run_ids': self.course_run.key,
            'course_uuids': self.course.uuid,
        })
        url = f'{self.url_base}/?{qs}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, self.error_message)
