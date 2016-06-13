import mock
from django.core.urlresolvers import reverse
from rest_framework.test import APITestCase

from course_catalog.apps.core.tests.factories import UserFactory


class RefreshCourseMetadataTests(APITestCase):
    """ Tests for the refresh_course_metadata management endpoint. """
    path = reverse('api:v1:management-refresh-course-metadata')
    call_command_path = 'course_catalog.apps.api.v1.views.call_command'

    def setUp(self):
        super(RefreshCourseMetadataTests, self).setUp()
        self.superuser = UserFactory(is_superuser=True)
        self.client.force_authenticate(self.superuser)  # pylint: disable=no-member

    def assert_access_forbidden(self):
        """ Asserts that a call to the endpoint fails with HTTP status 403. """
        response = self.client.post(self.path)
        self.assertEqual(response.status_code, 403)

    def test_superuser_required(self):
        """ Verify only superusers can access the endpoint. """
        with mock.patch(self.call_command_path, return_value=None):
            response = self.client.post(self.path)
            self.assertEqual(response.status_code, 200)

        # Anonymous user
        self.client.logout()
        self.assert_access_forbidden()

        # Normal and staff users
        users = (UserFactory(), UserFactory(is_staff=True),)
        for user in users:
            self.client.force_authenticate(user)  # pylint: disable=no-member
            self.assert_access_forbidden()

    def test_success_response(self):
        """ Verify a successful response calls the management command and returns the plain text output. """
        self.assert_successful_response()
        self.assert_successful_response('abc123')

    def assert_successful_response(self, access_token=None):
        """ Asserts the endpoint called the refresh_course_metadata management command with the correct arguments,
        and the endpoint returns HTTP 200 with text/plain content type. """
        data = {'access_token': access_token} if access_token else None
        with mock.patch(self.call_command_path, return_value=None) as mocked_call_command:
            response = self.client.post(self.path, data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, 'text/plain')

        args, kwargs = mocked_call_command.call_args
        expected = {
            'settings': 'course_catalog.settings.test'
        }
        if access_token:
            expected['access_token'] = access_token

        self.assertTrue(mocked_call_command.called)
        self.assertEqual(args[0], 'refresh_course_metadata')
        self.assertDictContainsSubset(expected, kwargs)
