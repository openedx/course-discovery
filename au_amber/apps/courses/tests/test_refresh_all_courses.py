""" Tests for Refresh All Courses management command. """

from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings
from edx_rest_api_client.client import EdxRestApiClient
from mock import patch

from au_amber.apps.courses.models import Course


@override_settings(
    SOCIAL_AUTH_EDX_OIDC_URL_ROOT="http://auth-url.com/oauth2",
    SOCIAL_AUTH_EDX_OIDC_KEY="client_id",
    SOCIAL_AUTH_EDX_OIDC_SECRET="client_secret"
)
class RefreshAllCoursesCommandTests(TestCase):
    """ Tests for refresh_all_courses management command. """
    cmd = 'refresh_all_courses'

    def test_call_with_access_token(self):
        """ Verify the management command calls Course.refresh_all() with access token. """
        access_token = 'secret'

        with patch.object(Course, 'refresh_all') as mock_refresh:
            call_command(self.cmd, access_token=access_token)
            mock_refresh.assert_called_once_with(access_token=access_token)

    def test_call_with_client_credentials(self):
        """ Verify the management command calls Course.refresh_all() with client credentials. """
        access_token = 'secret'

        with patch.object(EdxRestApiClient, 'get_oauth_access_token') as mock_access_token:
            mock_access_token.return_value = (access_token, None)
            with patch.object(Course, 'refresh_all') as mock_refresh:
                call_command(self.cmd)
                mock_refresh.assert_called_once_with(access_token=access_token)

    def test_call_with_client_credentials_error(self):
        """ Verify the command requires an access token to complete. """
        with patch.object(EdxRestApiClient, 'get_oauth_access_token') as mock_access_token:
            mock_access_token.side_effect = Exception()
            with self.assertRaises(Exception):
                call_command(self.cmd)
