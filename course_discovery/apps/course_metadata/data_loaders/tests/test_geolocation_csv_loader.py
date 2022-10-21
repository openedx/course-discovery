"""
Unit tests for Geolocation CSV Data loader.
"""
from tempfile import NamedTemporaryFile
from unittest import mock

import ddt
from testfixtures import LogCapture

from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase, OAuth2Mixin
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.data_loaders.geolocation_loader import GeolocationCSVDataLoader
from course_discovery.apps.course_metadata.data_loaders.tests import mock_data
from course_discovery.apps.course_metadata.data_loaders.tests.mixins import GeolocationCSVLoaderMixin
from course_discovery.apps.course_metadata.models import GeoLocation


@ddt.ddt
@mock.patch(
    'course_discovery.apps.course_metadata.data_loaders.configured_jwt_decode_handler',
    return_value={'preferred_username': 'test_username'}
)
class TestGeolocationCSVDataLoader(GeolocationCSVLoaderMixin, OAuth2Mixin, APITestCase):
    """
    Test Suite for GeolocationCSVDataLoader.
    """
    LOGGER_PATH = 'course_discovery.apps.course_metadata.data_loaders.geolocation_loader'
    INITIATED_LOG_MESSAGE = (LOGGER_PATH, 'INFO', 'Initiating Geolocation CSV data loader flow.')
    COMPLETED_LOG_MESSAGE = (LOGGER_PATH, 'INFO', 'Geolocation CSV loader ingest pipeline has completed.')
    SKIPPED_ITEMS_LOG_MESSAGE = (LOGGER_PATH, 'INFO', 'Skipped items:')

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
            self.INITIATED_LOG_MESSAGE,
            self.COMPLETED_LOG_MESSAGE
        )

    def test_data_validation_failure(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Verify that data validation fails given an invalid data.
        """

        field_name = 'PRODUCT TYPE'
        field_error_name = 'product_type'
        initial_geolocation_obj_count = GeoLocation.objects.count()
        INVALID_GEOLOCATION_CSV_DICT = {
            **mock_data.VALID_GEOLOCATION_CSV_DICT,
            field_name: 'ABC123'
        }

        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [INVALID_GEOLOCATION_CSV_DICT])
            with LogCapture(self.LOGGER_PATH) as log_capture:
                loader = GeolocationCSVDataLoader(self.partner, csv_path=csv.name)
                loader.ingest()
                self._assert_default_logs(log_capture)

                log_capture.check_present(
                    self.INITIATED_LOG_MESSAGE,
                    (
                        self.LOGGER_PATH,
                        'ERROR',
                        'Data validation issue for product with UUID: {}.'
                        'Skipping ingestion for this item.'
                        'Details: Wrong {} value for UUID: {}, Course or Program with UUID {} was not found'
                        .format(
                            INVALID_GEOLOCATION_CSV_DICT['UUID'],
                            field_error_name,
                            INVALID_GEOLOCATION_CSV_DICT['UUID'],
                            INVALID_GEOLOCATION_CSV_DICT['UUID']
                        )
                    ),
                    self.COMPLETED_LOG_MESSAGE,
                    self.SKIPPED_ITEMS_LOG_MESSAGE,
                    (
                        self.LOGGER_PATH,
                        'ERROR',
                        'Skipped {} with UUID {}. Errors: Wrong {} value for UUID: {}, '
                        'Course or Program with UUID {} was not found'
                        .format(
                            INVALID_GEOLOCATION_CSV_DICT['PRODUCT TYPE'].lower(),
                            INVALID_GEOLOCATION_CSV_DICT['UUID'],
                            field_error_name,
                            INVALID_GEOLOCATION_CSV_DICT['UUID'],
                            INVALID_GEOLOCATION_CSV_DICT['UUID']
                        )
                    )
                )
                assert GeoLocation.objects.count() == initial_geolocation_obj_count

    @ddt.data('course', 'program')
    def test_missing_product_validation_failure(self, product_type, jwt_decode_patch):  # pylint: disable=unused-argument
        initial_geolocation_obj_count = GeoLocation.objects.count()
        INVALID_GEOLOCATION_CSV_DICT = {
            **mock_data.VALID_GEOLOCATION_CSV_DICT,
            'PRODUCT_TYPE': product_type
        }

        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [INVALID_GEOLOCATION_CSV_DICT])
            with LogCapture(self.LOGGER_PATH) as log_capture:
                loader = GeolocationCSVDataLoader(self.partner, csv_path=csv.name)
                loader.ingest()
                self._assert_default_logs(log_capture)

                log_capture.check_present(
                    self.INITIATED_LOG_MESSAGE,
                    (
                        self.LOGGER_PATH,
                        'ERROR',
                        'Data validation issue for product with UUID: {}.'
                        'Skipping ingestion for this item.'
                        'Details: Course or Program with UUID {} was not found'
                        .format(
                            INVALID_GEOLOCATION_CSV_DICT['UUID'],
                            INVALID_GEOLOCATION_CSV_DICT['UUID']
                        )
                    ),
                    self.COMPLETED_LOG_MESSAGE,
                    self.SKIPPED_ITEMS_LOG_MESSAGE,
                    (
                        self.LOGGER_PATH,
                        'ERROR',
                        'Skipped course with UUID {}. Errors: Course or Program with UUID {} was not found'
                        .format(INVALID_GEOLOCATION_CSV_DICT['UUID'], INVALID_GEOLOCATION_CSV_DICT['UUID'])
                    )
                )
                assert GeoLocation.objects.count() == initial_geolocation_obj_count

    def test_uuid_validation_failure(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Verify that data validation fails given an invalid uuid.
        """
        invalid_uuid = 'xyz123'
        initial_geolocation_obj_count = GeoLocation.objects.count()
        INVALID_GEOLOCATION_CSV_DICT = {
            **mock_data.VALID_GEOLOCATION_CSV_DICT,
            'UUID': invalid_uuid
        }

        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [INVALID_GEOLOCATION_CSV_DICT])
            with LogCapture(self.LOGGER_PATH) as log_capture:
                loader = GeolocationCSVDataLoader(self.partner, csv_path=csv.name)
                loader.ingest()
                self._assert_default_logs(log_capture)

                log_capture.check_present(
                    self.INITIATED_LOG_MESSAGE,
                    (
                        self.LOGGER_PATH,
                        'ERROR',
                        'Data validation issue for product with UUID: {0}.'
                        'Skipping ingestion for this item.'
                        'Details: Invalid UUID: {0}'
                        .format(invalid_uuid)
                    ),
                    self.COMPLETED_LOG_MESSAGE,
                    self.SKIPPED_ITEMS_LOG_MESSAGE,
                    (
                        self.LOGGER_PATH,
                        'ERROR',
                        'Skipped course with UUID {bad_uuid}. Errors: Invalid UUID: {bad_uuid}'
                        .format(bad_uuid=invalid_uuid)
                    )
                )
                assert GeoLocation.objects.count() == initial_geolocation_obj_count

    @ddt.data('course', 'program')
    def test_product_success_flow(self, product_type, jwt_decode_patch):  # pylint: disable=unused-argument
        initial_geolocation_obj_count = GeoLocation.objects.count()
        VALID_PRODUCT_GEOLOCATION_CSV_DICT = {
            **mock_data.VALID_GEOLOCATION_CSV_DICT,
            'PRODUCT TYPE': product_type
        }
        valid_uuid = VALID_PRODUCT_GEOLOCATION_CSV_DICT['UUID']

        if product_type == 'program':
            self._setup_program(valid_uuid)
        else:
            self._setup_course(valid_uuid)

        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [VALID_PRODUCT_GEOLOCATION_CSV_DICT])
            with LogCapture(self.LOGGER_PATH) as log_capture:
                loader = GeolocationCSVDataLoader(self.partner, csv_path=csv.name)
                loader.ingest()
                self._assert_default_logs(log_capture)

                log_capture.check_present(
                    self.INITIATED_LOG_MESSAGE,
                    (
                        self.LOGGER_PATH,
                        'INFO',
                        'Starting data import flow for {}: {}'.format(product_type, valid_uuid)
                    ),
                    (
                        self.LOGGER_PATH,
                        'INFO',
                        'Updated geolocation data for product with UUID: {}'.format(valid_uuid)
                    ),
                    self.COMPLETED_LOG_MESSAGE,
                    (
                        self.LOGGER_PATH,
                        'INFO',
                        'Successfully updated {}s: '.format(product_type)
                    ),
                    (
                        self.LOGGER_PATH,
                        'INFO',
                        'Updated geolocation data for product with UUID: {}'.format(valid_uuid)
                    )
                )
                assert GeoLocation.objects.count() == initial_geolocation_obj_count + 1
