"""
Unit tests for import_degree_data management command.
"""
from unittest import mock

import responses
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from django.test import override_settings
from testfixtures import LogCapture

from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase, OAuth2Mixin
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.data_loaders.tests import mock_data
from course_discovery.apps.course_metadata.data_loaders.tests.mixins import DegreeCSVLoaderMixin
from course_discovery.apps.course_metadata.models import Curriculum, Degree, Program
from course_discovery.apps.course_metadata.tests.factories import DegreeDataLoaderConfigurationFactory

LOGGER_PATH = 'course_discovery.apps.course_metadata.management.commands.import_degree_data'


@mock.patch(
    'course_discovery.apps.course_metadata.data_loaders.configured_jwt_decode_handler',
    return_value={'preferred_username': 'test_username'}
)
class TestImportDegreeData(DegreeCSVLoaderMixin, OAuth2Mixin, APITestCase):
    """
    Test suite for import_degree_data management command.
    """
    def setUp(self) -> None:
        super().setUp()
        self.mock_access_token()
        self.user = UserFactory.create(username="test_user", password=USER_PASSWORD, is_staff=True)
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        csv_file_content = ','.join(list(mock_data.VALID_DEGREE_CSV_DICT)) + '\n'
        csv_file_content += ','.join(f'"{key}"' for key in list(
            mock_data.VALID_DEGREE_CSV_DICT.values()))
        self.csv_file = SimpleUploadedFile(
            name='test.csv',
            content=csv_file_content.encode('utf-8'),
            content_type='text/csv'
        )

    def test_missing_partner(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Test that the command raises CommandError if no partner is present against the provided short code.
        """
        with self.assertRaisesMessage(CommandError, 'Unable to locate partner with code invalid-partner-code'):
            call_command(
                'import_degree_data', '--partner_code', 'invalid-partner-code',
                '--product_source', self.product_source.slug,
            )

    def test_missing_source(self, _jwt_decode_patch):
        """
        Test that the command raises CommandError if no partner is present against the provided short code.
        """
        with self.assertRaisesMessage(CommandError, 'Unable to locate Product Source with code invalid-product-source'):
            call_command(
                'import_degree_data', '--partner_code', self.partner.short_code,
                '--product_source', 'invalid-product-source',
            )

    def test_invalid_csv_path(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Test that the command raises CommandError if an invalid csv path is provided.
        """
        _ = DegreeDataLoaderConfigurationFactory.create(enabled=True)
        with self.assertRaisesMessage(
                CommandError, 'CSV loader import could not be completed due to unexpected errors.'
        ):
            call_command(
                'import_degree_data', '--partner_code', self.partner.short_code, '--csv_path', 'no-path',
                '--product_source', self.product_source.slug,
            )

    def test_no_csv_file(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Test that the command raises ValueError if no csv file is provided.
        """
        _ = DegreeDataLoaderConfigurationFactory.create(enabled=True)
        with self.assertRaisesMessage(
                CommandError, "The 'csv_file' attribute has no file associated with it."
        ):
            call_command(
                'import_degree_data', '--partner_code', self.partner.short_code,
                '--product_source', self.product_source.slug,
            )

    @responses.activate
    @override_settings(PRODUCT_METADATA_MAPPING={'DEGREES': {'text-source': {'EMAIL_NOTIFICATION_LIST': []}}})
    @mock.patch('course_discovery.apps.course_metadata.management.commands.import_degree_data.send_ingestion_email')
    def test_success_flow(self, email_patch, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Verify that for a single row of valid data, the command completes CSV loader ingestion flow successfully.
        """
        self._setup_prerequisites(self.partner)
        _, image_content = self.mock_image_response()

        _ = DegreeDataLoaderConfigurationFactory.create(enabled=True, csv_file=self.csv_file)

        with LogCapture(LOGGER_PATH) as log_capture:
            call_command(
                'import_degree_data',
                '--partner_code', self.partner.short_code,
                '--product_type', 'DEGREES',
                '--product_source', self.product_source.slug,
            )
            log_capture.check_present(
                (
                    LOGGER_PATH,
                    'INFO',
                    'Starting CSV loader import flow for partner {}'.format(self.partner.short_code)
                )
            )
            log_capture.check_present(
                (LOGGER_PATH, 'INFO', 'CSV loader import flow completed.'),
                (LOGGER_PATH, 'INFO', 'Sending Ingestion stats email for product type DEGREES'),
            )

            assert Degree.objects.count() == 1
            assert Program.objects.count() == 1
            assert Curriculum.objects.count() == 1

            degree = Degree.objects.get(title=self.DEGREE_TITLE, partner=self.partner)
            program = Program.objects.get(degree=degree, partner=self.partner)
            curriculam = Curriculum.objects.get(program=program)

            assert degree.specializations.count() == 2
            assert curriculam.marketing_text == self.marketing_text
            assert degree.card_image.read() == image_content
            self._assert_degree_data(degree, self.BASE_EXPECTED_DEGREE_DATA)
            email_patch.assert_called_once()

    @responses.activate
    @override_settings(PRODUCT_METADATA_MAPPING={'DEGREES': {'text-source': {'EMAIL_NOTIFICATION_LIST': []}}})
    @mock.patch('course_discovery.apps.course_metadata.management.commands.import_degree_data.send_ingestion_email')
    def test_success_flow_with_org_mapping(self, email_patch, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Verify that for a single row of valid data, the command completes CSV loader ingestion flow successfully.
        """
        self._setup_prerequisites(self.partner, True)
        _, image_content = self.mock_image_response()

        csv_file_content = ','.join(list(mock_data.DEGREE_WITH_ORG_KEY_COLLISION_CSV_DICT)) + '\n'
        csv_file_content += ','.join(f'"{key}"' for key in list(
            mock_data.DEGREE_WITH_ORG_KEY_COLLISION_CSV_DICT.values()))
        self.csv_file = SimpleUploadedFile(
            name='test.csv',
            content=csv_file_content.encode('utf-8'),
            content_type='text/csv'
        )
        _ = DegreeDataLoaderConfigurationFactory.create(enabled=True, csv_file=self.csv_file)

        with LogCapture(LOGGER_PATH) as log_capture:
            call_command(
                'import_degree_data',
                '--partner_code', self.partner.short_code,
                '--product_type', 'DEGREES',
                '--product_source', self.product_source.slug,
            )
            log_capture.check_present(
                (
                    LOGGER_PATH,
                    'INFO',
                    'Starting CSV loader import flow for partner {}'.format(self.partner.short_code)
                )
            )
            log_capture.check_present(
                (LOGGER_PATH, 'INFO', 'CSV loader import flow completed.'),
                (LOGGER_PATH, 'INFO', 'Sending Ingestion stats email for product type DEGREES'),
            )

            assert Degree.objects.count() == 1
            assert Program.objects.count() == 1
            assert Curriculum.objects.count() == 1

            degree = Degree.objects.get(title=self.DEGREE_TITLE, partner=self.partner)
            program = Program.objects.get(degree=degree, partner=self.partner)
            curriculam = Curriculum.objects.get(program=program)

            assert degree.specializations.count() == 2
            assert curriculam.marketing_text == self.marketing_text
            assert degree.card_image.read() == image_content
            self._assert_degree_data(degree, self.BASE_EXPECTED_DEGREE_DATA)
            email_patch.assert_called_once()
