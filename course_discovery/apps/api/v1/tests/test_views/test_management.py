import mock
from django.core.urlresolvers import reverse
from rest_framework.test import APITestCase

from course_discovery.apps.core.tests.factories import UserFactory


class ManagementCommandViewTestMixin(object):
    call_command_path = None
    command_name = None
    path = None

    def setUp(self):
        super(ManagementCommandViewTestMixin, self).setUp()
        self.superuser = UserFactory(is_superuser=True)
        self.client.force_authenticate(self.superuser)  # pylint: disable=no-member

    def assert_access_forbidden(self):
        """ Asserts that a call to the endpoint fails with HTTP status 403. """
        response = self.client.post(self.path)
        self.assertEqual(response.status_code, 403)

    def test_non_superusers_denied(self):
        """ Verify access is denied to non-superusers. """
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
        """ Asserts the endpoint called the correct management command with the correct arguments, and the endpoint
        returns HTTP 200 with text/plain content type. """
        data = {'access_token': access_token} if access_token else None
        with mock.patch(self.call_command_path, return_value=None) as mocked_call_command:
            response = self.client.post(self.path, data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, 'text/plain')

        args, kwargs = mocked_call_command.call_args
        expected = {
            'settings': 'course_discovery.settings.test'
        }

        self.assertTrue(mocked_call_command.called)
        self.assertEqual(args[0], self.command_name)
        self.assertDictContainsSubset(expected, kwargs)


class UpdateIndexTests(ManagementCommandViewTestMixin, APITestCase):
    """ Tests for the update_index management endpoint. """
    call_command_path = 'course_discovery.apps.api.v1.views.call_command'
    command_name = 'update_index'
    path = reverse('api:v1:management-update-index')
