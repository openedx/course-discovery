# pylint: disable=redefined-builtin

import ddt
import responses
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from course_discovery.apps.api.v1.tests.test_views.mixins import SerializationMixin, OAuth2Mixin
from course_discovery.apps.core.tests.factories import UserFactory, USER_PASSWORD
from course_discovery.apps.core.tests.mixins import ElasticsearchTestMixin
from course_discovery.apps.course_metadata.tests.factories import CourseFactory


@ddt.ddt
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

        response = self.client.get(url, {'format': format, 'limit': limit})
        self.assertEqual(response.status_code, 200)
        self.assertListEqual(response.data['results'], self.serialize_course(courses[:limit], many=True, format=format))

        response.render()

    def test_retrieve(self):
        """ Verify the endpoint returns a single course. """
        self.assert_retrieve_success()

    def assert_retrieve_success(self, **headers):
        """ Asserts the endpoint returns details for a single course. """
        course = CourseFactory()
        url = reverse('api:v1:course-detail', kwargs={'key': course.key})
        response = self.client.get(url, format='json', **headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.serialize_course(course))

    @responses.activate
    def test_retrieve_with_oauth2_authentication(self):
        self.client.logout()
        self.mock_user_info_response(self.user)
        self.assert_retrieve_success(HTTP_AUTHORIZATION=self.generate_oauth2_token_header(self.user))
