import mock
from django.core.management import CommandError, call_command
from django.test import TestCase


class RefreshAllCoursesCommandTests(TestCase):
    cmd = 'refresh_all_courses'

    def test_call(self):
        """ Verify the management command calls Course.refresh_all(). """
        access_token = 'secret'

        with mock.patch('course_discovery.apps.courses.models.Course.refresh_all') as mock_refresh:
            call_command(self.cmd, access_token=access_token)
            mock_refresh.assert_called_once_with(access_token=access_token)

    def test_call_without_access_token(self):
        """ Verify the command requires an access token. """
        with self.assertRaisesRegex(CommandError, 'Courses cannot be migrated if no access token is supplied.'):
            call_command(self.cmd)
