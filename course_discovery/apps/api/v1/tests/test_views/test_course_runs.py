from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from course_discovery.apps.api.serializers import CourseRunSerializer
from course_discovery.apps.core.tests.factories import UserFactory, USER_PASSWORD
from course_discovery.apps.course_metadata.tests.factories import CourseRunFactory
from course_discovery.apps.course_metadata.models import CourseRun


class CourseRunViewSetTests(APITestCase):
    def setUp(self):
        super(CourseRunViewSetTests, self).setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.client.login(username=self.user.username, password=USER_PASSWORD)
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
        self.assertListEqual(response.data['results'], CourseRunSerializer(CourseRun.objects.all(), many=True).data)
