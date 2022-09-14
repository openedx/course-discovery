"""
Unit tests for Geotargeting CSV Data loader.
"""
from tempfile import NamedTemporaryFile
from unittest import mock

import ddt
from testfixtures import LogCapture

from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase, OAuth2Mixin
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.data_loaders.geotargeting_loader import GeotargetingCSVDataLoader
from course_discovery.apps.course_metadata.data_loaders.tests import mock_data
from course_discovery.apps.course_metadata.data_loaders.tests.mixins import GeotargetingCSVLoaderMixin
from course_discovery.apps.course_metadata.models import CourseLocationRestriction, ProgramLocationRestriction

LOGGER_PATH = 'course_discovery.apps.course_metadata.data_loaders.geotargeting_loader'
INITIATED_LOG_MESSAGE = (LOGGER_PATH, 'INFO', 'Initiating Geotargeting CSV data loader flow.')
COMPLETED_LOG_MESSAGE = (LOGGER_PATH, 'INFO', 'Geotargeting CSV loader ingest pipeline has completed.')
SKIPPED_ITEMS_LOG_MESSAGE = (LOGGER_PATH, 'INFO', 'Skipped items:')


@ddt.ddt
@mock.patch(
    'course_discovery.apps.course_metadata.data_loaders.configured_jwt_decode_handler',
    return_value={'preferred_username': 'test_username'}
)
class TestGeotargetingCSVDataLoader(GeotargetingCSVLoaderMixin, OAuth2Mixin, APITestCase):
    """
    Test Suite for DegreeCSVLoader.
    """

    def setUp(self) -> None:
        super().setUp()
        self.mock_access_token()
        self.user = UserFactory.create(username="test_user", password=USER_PASSWORD, is_staff=True)
        self.client.login(username=self.user.username, password=USER_PASSWORD)

    def _assert_default_logs(self, log_capture):
        """
        Assert the initiation and completion logs are present in the logger.
        """
        log_capture.check_present(
            INITIATED_LOG_MESSAGE,
            COMPLETED_LOG_MESSAGE
        )

    @ddt.data('PRODUCT TYPE', 'INCLUDE OR EXCLUDE')
    def test_data_validation_failure(self, field_name, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Verify that data validation fails given an invalid data.
        """
        INVALID_GEOTARGETING_CSV_DICT = {
            **mock_data.VALID_GEOTARGETING_CSV_DICT,
            field_name: 'ABC123'
        }

        field_error_name = ''

        if field_name == 'PRODUCT TYPE':
            field_error_name = 'product_type'
        elif field_name == 'INCLUDE OR EXCLUDE':
            field_error_name = 'include/exclude'

        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [INVALID_GEOTARGETING_CSV_DICT])
            with LogCapture(LOGGER_PATH) as log_capture:
                loader = GeotargetingCSVDataLoader(self.partner, csv_path=csv.name)
                loader.ingest()
                self._assert_default_logs(log_capture)

                log_capture.check_present(
                    INITIATED_LOG_MESSAGE,
                    (
                        LOGGER_PATH,
                        'ERROR',
                        'Data validation issue for product with UUID: {}. Skipping ingestion for this item.'
                        .format(INVALID_GEOTARGETING_CSV_DICT['UUID'])
                    ),
                    (
                        LOGGER_PATH,
                        'ERROR',
                        'Details: Wrong {} value for UUID: {}, Course or Program with UUID {} was not found\n'
                        .format(
                            field_error_name,
                            INVALID_GEOTARGETING_CSV_DICT['UUID'],
                            INVALID_GEOTARGETING_CSV_DICT['UUID']
                        )
                    ),
                    COMPLETED_LOG_MESSAGE,
                    SKIPPED_ITEMS_LOG_MESSAGE,
                    (
                        LOGGER_PATH,
                        'ERROR',
                        'Skipped {} with UUID {}. Errors: Wrong {} value for UUID: {}, '
                        'Course or Program with UUID {} was not found'
                        .format(
                            INVALID_GEOTARGETING_CSV_DICT['PRODUCT TYPE'].lower(),
                            INVALID_GEOTARGETING_CSV_DICT['UUID'],
                            field_error_name,
                            INVALID_GEOTARGETING_CSV_DICT['UUID'],
                            INVALID_GEOTARGETING_CSV_DICT['UUID']
                        )
                    )
                )
                assert CourseLocationRestriction.objects.count() == 0
                assert ProgramLocationRestriction.objects.count() == 0

    @ddt.data('XX', 'US;XX', 'XX;PL')
    def test_country_code_validation_failure(self, countries, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Verify that data validation fails given an invalid country code list.
        """
        INVALID_GEOTARGETING_CSV_DICT = {
            **mock_data.VALID_GEOTARGETING_CSV_DICT,
            'Countries': countries
        }

        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [INVALID_GEOTARGETING_CSV_DICT])
            with LogCapture(LOGGER_PATH) as log_capture:
                loader = GeotargetingCSVDataLoader(self.partner, csv_path=csv.name)
                loader.ingest()
                self._assert_default_logs(log_capture)

                log_capture.check_present(
                    INITIATED_LOG_MESSAGE,
                    (
                        LOGGER_PATH,
                        'ERROR',
                        'Data validation issue for product with UUID: {}. Skipping ingestion for this item.'
                        .format(INVALID_GEOTARGETING_CSV_DICT['UUID'])
                    ),
                    (
                        LOGGER_PATH,
                        'ERROR',
                        'Details: Error in the countries list for UUID: {}, '
                        'Course or Program with UUID {} was not found\n'
                        .format(INVALID_GEOTARGETING_CSV_DICT['UUID'], INVALID_GEOTARGETING_CSV_DICT['UUID'])
                    ),
                    COMPLETED_LOG_MESSAGE,
                    SKIPPED_ITEMS_LOG_MESSAGE,
                    (
                        LOGGER_PATH,
                        'ERROR',
                        'Skipped course with UUID {}. Errors: Error in the countries list for UUID: {}, '
                        'Course or Program with UUID {} was not found'
                        .format(
                            INVALID_GEOTARGETING_CSV_DICT['UUID'],
                            INVALID_GEOTARGETING_CSV_DICT['UUID'],
                            INVALID_GEOTARGETING_CSV_DICT['UUID']
                        )
                    )
                )

                assert CourseLocationRestriction.objects.count() == 0
                assert ProgramLocationRestriction.objects.count() == 0

    @ddt.data('Course', 'Program')
    def test_missing_product_validation_failure(self, product_type, jwt_decode_patch):  # pylint: disable=unused-argument
        INVALID_GEOTARGETING_CSV_DICT = {
            **mock_data.VALID_GEOTARGETING_CSV_DICT,
            'PRODUCT_TYPE': product_type
        }

        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [INVALID_GEOTARGETING_CSV_DICT])
            with LogCapture(LOGGER_PATH) as log_capture:
                loader = GeotargetingCSVDataLoader(self.partner, csv_path=csv.name)
                loader.ingest()
                self._assert_default_logs(log_capture)

                log_capture.check_present(
                    INITIATED_LOG_MESSAGE,
                    (
                        LOGGER_PATH,
                        'ERROR',
                        'Data validation issue for product with UUID: {}. Skipping ingestion for this item.'
                        .format(INVALID_GEOTARGETING_CSV_DICT['UUID'])
                    ),
                    (
                        LOGGER_PATH,
                        'ERROR',
                        'Details: Course or Program with UUID {} was not found\n'
                        .format(INVALID_GEOTARGETING_CSV_DICT['UUID'])
                    ),
                    COMPLETED_LOG_MESSAGE,
                    SKIPPED_ITEMS_LOG_MESSAGE,
                    (
                        LOGGER_PATH,
                        'ERROR',
                        'Skipped course with UUID {}. Errors: Course or Program with UUID {} was not found'
                        .format(INVALID_GEOTARGETING_CSV_DICT['UUID'], INVALID_GEOTARGETING_CSV_DICT['UUID'])
                    )
                )
                assert CourseLocationRestriction.objects.count() == 0
                assert ProgramLocationRestriction.objects.count() == 0

    def test_uuid_validation_failure(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Verify that data validation fails given an invalid uuid.
        """
        invalid_uuid = 'xyz123'
        INVALID_GEOTARGETING_CSV_DICT = {
            **mock_data.VALID_GEOTARGETING_CSV_DICT,
            'UUID': invalid_uuid
        }

        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [INVALID_GEOTARGETING_CSV_DICT])
            with LogCapture(LOGGER_PATH) as log_capture:
                loader = GeotargetingCSVDataLoader(self.partner, csv_path=csv.name)
                loader.ingest()
                self._assert_default_logs(log_capture)

                log_capture.check_present(
                    INITIATED_LOG_MESSAGE,
                    (
                        LOGGER_PATH,
                        'ERROR',
                        'Data validation issue for product with UUID: {}. Skipping ingestion for this item.'
                        .format(invalid_uuid)
                    ),
                    (
                        LOGGER_PATH,
                        'ERROR',
                        'Details: Invalid UUID: {}\n'.format(invalid_uuid)
                    ),
                    COMPLETED_LOG_MESSAGE,
                    SKIPPED_ITEMS_LOG_MESSAGE,
                    (
                        LOGGER_PATH,
                        'ERROR',
                        'Skipped course with UUID {bad_uuid}. Errors: Invalid UUID: {bad_uuid}'
                        .format(bad_uuid=invalid_uuid)
                    )
                )
                assert CourseLocationRestriction.objects.count() == 0
                assert ProgramLocationRestriction.objects.count() == 0

    def test_course_success_flow(self, jwt_decode_patch):  # pylint: disable=unused-argument
        valid_uuid = mock_data.VALID_GEOTARGETING_CSV_DICT['UUID']
        self._setup_course(valid_uuid)

        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [mock_data.VALID_GEOTARGETING_CSV_DICT])
            with LogCapture(LOGGER_PATH) as log_capture:
                loader = GeotargetingCSVDataLoader(self.partner, csv_path=csv.name)
                loader.ingest()
                self._assert_default_logs(log_capture)

                log_capture.check_present(
                    INITIATED_LOG_MESSAGE,
                    (
                        LOGGER_PATH,
                        'INFO',
                        'Starting data import flow for course: {}'.format(valid_uuid)
                    ),
                    (
                        LOGGER_PATH,
                        'INFO',
                        'Created geotargeting data for course with UUID: {}'.format(valid_uuid)
                    ),
                    COMPLETED_LOG_MESSAGE,
                    (
                        LOGGER_PATH,
                        'INFO',
                        'Successfully updated courses: '
                    ),
                    (
                        LOGGER_PATH,
                        'INFO',
                        'Created geotargeting data for course with UUID: {}'.format(valid_uuid)
                    )
                )
                assert CourseLocationRestriction.objects.count() == 1
                assert ProgramLocationRestriction.objects.count() == 0

    def test_program_success_flow(self, jwt_decode_patch):  # pylint: disable=unused-argument
        VALID_PROGRAM_GEOTARGETING_CSV_DICT = {
            **mock_data.VALID_GEOTARGETING_CSV_DICT,
            'PRODUCT TYPE': 'Program'
        }
        valid_uuid = VALID_PROGRAM_GEOTARGETING_CSV_DICT['UUID']
        self._setup_program(valid_uuid)

        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [VALID_PROGRAM_GEOTARGETING_CSV_DICT])
            with LogCapture(LOGGER_PATH) as log_capture:
                loader = GeotargetingCSVDataLoader(self.partner, csv_path=csv.name)
                loader.ingest()
                self._assert_default_logs(log_capture)

                log_capture.check_present(
                    INITIATED_LOG_MESSAGE,
                    (
                        LOGGER_PATH,
                        'INFO',
                        'Starting data import flow for program: {}'.format(valid_uuid)
                    ),
                    (
                        LOGGER_PATH,
                        'INFO',
                        'Created geotargeting data for program with UUID: {}'.format(valid_uuid)
                    ),
                    COMPLETED_LOG_MESSAGE,
                    (
                        LOGGER_PATH,
                        'INFO',
                        'Successfully updated programs: '
                    ),
                    (
                        LOGGER_PATH,
                        'INFO',
                        'Created geotargeting data for program with UUID: {}'.format(valid_uuid)
                    )
                )
                assert CourseLocationRestriction.objects.count() == 0
                assert ProgramLocationRestriction.objects.count() == 1
