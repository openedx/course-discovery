"""
Unit tests for import_course_metadata management command.
"""
from unittest import mock

import responses
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from testfixtures import LogCapture

from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase, OAuth2Mixin
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.data_loaders.csv_loader import CSVDataLoader
from course_discovery.apps.course_metadata.data_loaders.tests import mock_data
from course_discovery.apps.course_metadata.data_loaders.tests.mixins import CSVLoaderMixin
from course_discovery.apps.course_metadata.models import Course, CourseRun
from course_discovery.apps.course_metadata.tests.factories import CSVDataLoaderConfigurationFactory

LOGGER_PATH = 'course_discovery.apps.course_metadata.management.commands.import_course_metadata'


@mock.patch(
    'course_discovery.apps.course_metadata.data_loaders.configured_jwt_decode_handler',
    return_value={'preferred_username': 'test_username'}
)
class TestImportCourseMetadata(CSVLoaderMixin, OAuth2Mixin, APITestCase):
    """
    Test suite for import_course_metadata management command.
    """
    def setUp(self) -> None:
        super().setUp()
        self.mock_access_token()
        self.user = UserFactory.create(username="test_user", password=USER_PASSWORD, is_staff=True)
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        csv_file_content = ','.join(list(mock_data.VALID_COURSE_AND_COURSE_RUN_CSV_DICT)) + '\n'
        csv_file_content += ','.join(f'"{key}"' for key in list(
            mock_data.VALID_COURSE_AND_COURSE_RUN_CSV_DICT.values()))
        self.csv_file = SimpleUploadedFile(
            name='test.csv',
            content=csv_file_content.encode('utf-8'),
            content_type='text/csv'
        )

    def mock_call_course_api(self, method, url, data):
        """
        Helper method to make api calls using test client.
        """
        response = None
        if method == 'POST':
            response = self.client.post(
                url,
                data=data,
                format='json'
            )
        elif method == 'PATCH':
            response = self.client.patch(
                url,
                data=data,
                format='json'
            )
        return response

    def test_no_csv_file(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Test that the command raises ValueError if no csv file is provided.
        """
        _ = CSVDataLoaderConfigurationFactory.create(enabled=True)
        with self.assertRaisesMessage(CommandError, "The 'csv_file' attribute has no file associated with it."):
            call_command(
                'import_course_metadata', '--partner_code', self.partner.short_code,
            )

    def test_invalid_csv_path(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Test that the command raises CommandError if an invalid csv path is provided.
        """
        _ = CSVDataLoaderConfigurationFactory.create(enabled=True)
        with self.assertRaisesMessage(
                CommandError, 'CSV loader import could not be completed due to unexpected errors.'
        ):
            call_command(
                'import_course_metadata', '--partner_code', self.partner.short_code, '--csv_path', 'no-path',
            )

    def test_missing_partner(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Test that the command raises CommandError if no partner is present against the provided short code.
        """
        _ = CSVDataLoaderConfigurationFactory.create(enabled=True, csv_file=self.csv_file)
        with self.assertRaisesMessage(CommandError, 'Unable to locate partner with code invalid-partner-code'):
            call_command(
                'import_course_metadata', '--partner_code', 'invalid-partner-code',
            )

    @responses.activate
    def test_success_flow(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Verify that for a single row of valid data, the command completes CSV loader ingestion flow successfully.
        """
        self._setup_prerequisites(self.partner)
        self.mock_studio_calls(self.partner)
        self.mock_ecommerce_publication(self.partner)
        _, image_content = self.mock_image_response()

        _ = CSVDataLoaderConfigurationFactory.create(enabled=True, csv_file=self.csv_file)

        with LogCapture(LOGGER_PATH) as log_capture:
            with mock.patch.object(
                    CSVDataLoader,
                    '_call_course_api',
                    self.mock_call_course_api
            ):
                call_command(
                    'import_course_metadata', '--partner_code', self.partner.short_code
                )
                log_capture.check_present(
                    (
                        LOGGER_PATH,
                        'INFO',
                        'Starting CSV loader import flow for partner {}'.format(self.partner.short_code)
                    )
                )
                log_capture.check_present(
                    (LOGGER_PATH, 'INFO', 'CSV loader import flow completed.')
                )

                assert Course.everything.count() == 1
                assert CourseRun.everything.count() == 1

                course = Course.everything.get(key=self.COURSE_KEY, partner=self.partner)
                course_run = CourseRun.everything.get(course=course)

                assert course.image.read() == image_content
                self._assert_course_data(course, self.BASE_EXPECTED_COURSE_DATA)
                self._assert_course_run_data(course_run, self.BASE_EXPECTED_COURSE_RUN_DATA)
