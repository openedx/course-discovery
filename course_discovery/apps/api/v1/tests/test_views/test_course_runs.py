# pylint: disable=no-member
from django.db.models.functions import Lower
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from course_discovery.apps.api.serializers import CourseRunSerializer
from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.course_metadata.tests.factories import CourseRunFactory
from course_discovery.apps.course_metadata.models import CourseRun


class CourseRunViewSetTests(APITestCase):
    def setUp(self):
        super(CourseRunViewSetTests, self).setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.client.force_authenticate(self.user)
        self.course_run = CourseRunFactory()

    def test_get(self):
        """ Verify the endpoint returns the details for a single course. """
        url = reverse('api:v1:course_run-detail', kwargs={'key': self.course_run.key})

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, CourseRunSerializer(self.course_run).data)

    def test_list(self):
        """ Verify the endpoint returns a list of all catalogs. """
        url = reverse('api:v1:course_run-list')

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertListEqual(
            response.data['results'],
            CourseRunSerializer(CourseRun.objects.all().order_by(Lower('key')), many=True).data
        )

    def test_list_query(self):
        """ Verify the endpoint returns a filtered list of courses """
        title = 'Some random course'
        course_runs = CourseRunFactory.create_batch(3, title=title)
        CourseRunFactory(title='non-matching name')
        query = 'title:' + title
        url = '{root}?q={query}'.format(root=reverse('api:v1:course_run-list'), query=query)

        response = self.client.get(url)
        actual_sorted = sorted(response.data['results'], key=lambda course_run: course_run['key'])
        expected_sorted = sorted(
            CourseRunSerializer(course_runs, many=True).data, key=lambda course_run: course_run['key']
        )
        self.assertListEqual(actual_sorted, expected_sorted)
