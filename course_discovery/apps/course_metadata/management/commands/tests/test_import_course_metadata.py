"""
Unit tests for import_course_metadata management command.
"""
from unittest import mock

import responses
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from edx_toggles.toggles.testutils import override_waffle_switch
from slugify import slugify
from testfixtures import LogCapture

from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase, OAuth2Mixin
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.data_loaders.csv_loader import CSVDataLoader
from course_discovery.apps.course_metadata.data_loaders.tests import mock_data
from course_discovery.apps.course_metadata.data_loaders.tests.mixins import CSVLoaderMixin
from course_discovery.apps.course_metadata.models import Course, CourseRun
from course_discovery.apps.course_metadata.tests.factories import CSVDataLoaderConfigurationFactory
from course_discovery.apps.course_metadata.toggles import (
    IS_SUBDIRECTORY_SLUG_FORMAT_ENABLED, IS_SUBDIRECTORY_SLUG_FORMAT_FOR_EXEC_ED_ENABLED
)

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
                'import_course_metadata',
                '--partner_code', self.partner.short_code,
                '--product_type', 'EXECUTIVE_EDUCATION',
                '--product_source', self.source.slug
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
                'import_course_metadata',
                '--partner_code', self.partner.short_code,
                '--product_type', 'EXECUTIVE_EDUCATION',
                '--product_source', self.source.slug,
                '--csv_path', 'no-path',
            )

    def test_missing_partner(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Test that the command raises CommandError if no partner is present against the provided short code.
        """
        _ = CSVDataLoaderConfigurationFactory.create(enabled=True, csv_file=self.csv_file)
        with self.assertRaisesMessage(CommandError, 'Unable to locate partner with code invalid-partner-code'):
            call_command(
                'import_course_metadata',
                '--partner_code', 'invalid-partner-code',
                '--product_type', 'EXECUTIVE_EDUCATION',
                '--product_source', self.source.slug,
            )

    def test_missing_product_source(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Test that the command raises CommandError if no source is present against the provided product source slug.
        """
        _ = CSVDataLoaderConfigurationFactory.create(enabled=True, csv_file=self.csv_file)
        with self.assertRaisesMessage(CommandError, 'Unable to locate Product Source with code invalid_slug'):
            call_command(
                'import_course_metadata',
                '--partner_code', self.partner.short_code,
                '--product_type', 'EXECUTIVE_EDUCATION',
                '--product_source', 'invalid_slug',
            )

    @responses.activate
    @mock.patch('course_discovery.apps.course_metadata.management.commands.import_course_metadata.send_ingestion_email')
    def test_success_flow(self, email_patch, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Verify that for a single row of valid data, the command completes CSV loader ingestion flow successfully.
        """
        self._setup_prerequisites(self.partner)
        self.mock_studio_calls(self.partner)
        self.mock_ecommerce_publication(self.partner)
        _, image_content = self.mock_image_response()

        _ = CSVDataLoaderConfigurationFactory.create(enabled=True, csv_file=self.csv_file)

        with override_waffle_switch(IS_SUBDIRECTORY_SLUG_FORMAT_ENABLED, active=True):
            with override_waffle_switch(IS_SUBDIRECTORY_SLUG_FORMAT_FOR_EXEC_ED_ENABLED, active=True):
                with LogCapture(LOGGER_PATH) as log_capture:
                    with mock.patch.object(
                            CSVDataLoader,
                            '_call_course_api',
                            self.mock_call_course_api
                    ):
                        call_command(
                            'import_course_metadata',
                            '--partner_code', self.partner.short_code,
                            '--product_type', 'EXECUTIVE_EDUCATION',
                            '--product_source', self.source.slug,
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

                        assert Course.everything.count() == 2
                        assert CourseRun.everything.count() == 2

                        course = Course.everything.get(key=self.COURSE_KEY, partner=self.partner, draft=True)
                        course_run = CourseRun.everything.get(course=course, draft=True)
                        slug_path = f'{slugify(course.authoring_organizations.first().name)}-{slugify(course.title)}'

                        assert course.image.read() == image_content
                        assert course.active_url_slug == f'executive-education/{slug_path}'
                        self._assert_course_data(course, self.BASE_EXPECTED_COURSE_DATA)
                        self._assert_course_run_data(course_run, self.BASE_EXPECTED_COURSE_RUN_DATA)
                        email_patch.assert_called_once()

    @responses.activate
    @mock.patch('course_discovery.apps.course_metadata.management.commands.import_course_metadata.send_ingestion_email')
    def test_exec_ed_slug__disabled_switch(self, _email_patch, _jwt_decode_patch):
        """
        Verify that if IS_SUBDIRECTORY_SLUG_FORMAT_FOR_EXEC_ED_ENABLED switch is disable url slug will not follow
        sub directory format
        """
        self._setup_prerequisites(self.partner)
        self.mock_studio_calls(self.partner)
        self.mock_ecommerce_publication(self.partner)

        _ = CSVDataLoaderConfigurationFactory.create(enabled=True, csv_file=self.csv_file)

        with override_waffle_switch(IS_SUBDIRECTORY_SLUG_FORMAT_ENABLED, active=True):
            with override_waffle_switch(IS_SUBDIRECTORY_SLUG_FORMAT_FOR_EXEC_ED_ENABLED, active=False):
                with LogCapture(LOGGER_PATH) as log_capture:
                    with mock.patch.object(
                            CSVDataLoader,
                            '_call_course_api',
                            self.mock_call_course_api
                    ):
                        call_command(
                            'import_course_metadata',
                            '--partner_code', self.partner.short_code,
                            '--product_type', 'EXECUTIVE_EDUCATION',
                            '--product_source', self.source.slug,
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

                        course = Course.everything.get(key=self.COURSE_KEY, partner=self.partner)
                        assert course.active_url_slug == slugify(course.title)
