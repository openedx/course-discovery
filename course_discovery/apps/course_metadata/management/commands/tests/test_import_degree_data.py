"""
Unit tests for import_degree_data management command.
"""
from tempfile import NamedTemporaryFile
from unittest import mock

import responses
from django.core.management import CommandError, call_command
from testfixtures import LogCapture

from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase, OAuth2Mixin
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.data_loaders.tests import mock_data
from course_discovery.apps.course_metadata.data_loaders.tests.mixins import DegreeCSVLoaderMixin
from course_discovery.apps.course_metadata.models import Curriculum, Degree, Program

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

    def test_missing_partner(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Test that the command raises CommandError if no partner is present against the provided short code.
        """
        with self.assertRaisesMessage(CommandError, 'Unable to locate partner with code invalid-partner-code'):
            call_command(
                'import_degree_data', '--partner_code', 'invalid-partner-code', '--csv_path', ''
            )

    def test_invalid_csv_path(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Test that the command raises CommandError if an invalid csv path is provided.
        """
        with self.assertRaisesMessage(
                CommandError, 'CSV loader import could not be completed due to unexpected errors.'
        ):
            call_command(
                'import_degree_data', '--partner_code', self.partner.short_code, '--csv_path', 'no-path'
            )

    @responses.activate
    def test_success_flow(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Verify that for a single row of valid data, the command completes CSV loader ingestion flow successfully.
        """
        self._setup_prerequisites(self.partner)
        _, image_content = self.mock_image_response()

        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [mock_data.VALID_DEGREE_CSV_DICT])

            with LogCapture(LOGGER_PATH) as log_capture:
                call_command(
                    'import_degree_data', '--csv_path', csv.name, '--partner_code', self.partner.short_code
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
