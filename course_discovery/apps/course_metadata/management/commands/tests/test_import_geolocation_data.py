"""
Unit tests for import_geolocation_data management command.
"""
from unittest import mock
from uuid import UUID

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command

from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase, OAuth2Mixin
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.data_loaders.tests import mock_data
from course_discovery.apps.course_metadata.data_loaders.tests.mixins import GeolocationCSVLoaderMixin
from course_discovery.apps.course_metadata.models import Course
from course_discovery.apps.course_metadata.tests.factories import GeolocationDataLoaderConfigurationFactory

LOGGER_PATH = 'course_discovery.apps.course_metadata.management.commands.import_geolocation_data'


@mock.patch(
    'course_discovery.apps.course_metadata.data_loaders.configured_jwt_decode_handler',
    return_value={'preferred_username': 'test_username'}
)
class TestImportGeolocationData(GeolocationCSVLoaderMixin, OAuth2Mixin, APITestCase):
    """
    Test suite for import_geolocation_data management command.
    """
    def setUp(self) -> None:
        super().setUp()
        self.mock_access_token()
        self.user = UserFactory.create(username="test_user", password=USER_PASSWORD, is_staff=True)
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.geolocation_sample = {**mock_data.VALID_GEOLOCATION_CSV_DICT, 'LOCATION NAME': 'mit'}
        csv_file_content = ','.join(list(self.geolocation_sample)) + '\n'
        csv_file_content += ','.join(f'"{key}"' for key in list(
            self.geolocation_sample.values()))
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
                'import_geolocation_data', '--partner_code', 'invalid-partner-code',
            )

    def test_invalid_csv_path(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Test that the command raises CommandError if an invalid csv path is provided.
        """
        with self.assertRaisesMessage(
                CommandError, 'Geolocation CSV loader import could not be completed due to unexpected errors.'
        ):
            call_command(
                'import_geolocation_data', '--partner_code', self.partner.short_code, '--csv_path', 'no-path',
            )

    def test_no_csv_file(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Test that the command raises ValueError if no csv file is provided.
        """
        _ = GeolocationDataLoaderConfigurationFactory.create(enabled=True)
        with self.assertRaisesMessage(
                CommandError, "The 'csv_file' attribute has no file associated with it."
        ):
            call_command(
                'import_geolocation_data', '--partner_code', self.partner.short_code,
            )

    def test_success_flow(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Verify that for a single row of valid data, the command completes ingestion flow successfully.
        """
        self._setup_course('3f10df65fd0641df9b42ad2cbaeb7fee')
        course_obj = Course.everything.first()

        assert Course.everything.count() == 1
        assert course_obj.uuid == UUID('3f10df65fd0641df9b42ad2cbaeb7fee')

        _ = GeolocationDataLoaderConfigurationFactory.create(enabled=True, csv_file=self.csv_file)

        call_command('import_geolocation_data', '--partner_code', self.partner.short_code)

        course_obj_updated = Course.everything.first()
        assert course_obj_updated.geolocation is not None
        assert course_obj_updated.geolocation.location_name == self.geolocation_sample['LOCATION NAME']
