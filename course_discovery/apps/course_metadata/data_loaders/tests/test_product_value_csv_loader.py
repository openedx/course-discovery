"""
Unit tests for Product Value CSV Data loader.
"""
from tempfile import NamedTemporaryFile
from unittest import mock

import ddt
from testfixtures import LogCapture

from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase, OAuth2Mixin
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.data_loaders.product_value_loader import ProductValueCSVDataLoader
from course_discovery.apps.course_metadata.data_loaders.tests import mock_data
from course_discovery.apps.course_metadata.data_loaders.tests.mixins import ProductValueCSVLoaderMixin
from course_discovery.apps.course_metadata.models import Course, ProductValue, Program


@ddt.ddt
@mock.patch(
    'course_discovery.apps.course_metadata.data_loaders.configured_jwt_decode_handler',
    return_value={'preferred_username': 'test_username'}
)
class TestProductCSVDataLoader(ProductValueCSVLoaderMixin, OAuth2Mixin, APITestCase):
    """
    Test Suite for ProductValueCSVDataLoader.
    """
    LOGGER_PATH = 'course_discovery.apps.course_metadata.data_loaders.product_value_loader'
    INITIATED_LOG_MESSAGE = (LOGGER_PATH, 'INFO', 'Initiating Product Value CSV data loader flow.')
    PIPELINE_COMPLETED_LOG_MESSAGE = (LOGGER_PATH, 'INFO', 'Product Value CSV loader ingest pipeline has completed.')
    ORPHANED_PRODUCT_VALUE_CHECK_LOG_MESSAGE = (LOGGER_PATH, 'INFO', 'Checking for orphaned product value records.')
    COMPLETED_LOG_MESSAGE = (LOGGER_PATH, 'INFO', 'Product Value ingestion complete!')
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
        initial_product_value_obj_count = ProductValue.objects.count()
        INVALID_PRODUCT_VALUE_CSV_DICT = {
            **mock_data.VALID_PRODUCT_VALUE_CSV_DICT,
            field_name: 'ABC123'
        }

        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [INVALID_PRODUCT_VALUE_CSV_DICT])
            with LogCapture(self.LOGGER_PATH) as log_capture:
                loader = ProductValueCSVDataLoader(self.partner, csv_path=csv.name)
                loader.ingest()
                self._assert_default_logs(log_capture)

                log_capture.check_present(
                    self.INITIATED_LOG_MESSAGE,
                    (
                        self.LOGGER_PATH,
                        'ERROR',
                        'Data validation issue for product with UUID: {}.'
                        ' Skipping ingestion for this item.'
                        ' Details: Wrong {} value for UUID: {},'
                        ' Unable to validate that product exists due to invalid Product Type'
                        .format(
                            INVALID_PRODUCT_VALUE_CSV_DICT['UUID'],
                            field_error_name,
                            INVALID_PRODUCT_VALUE_CSV_DICT['UUID'],
                        )
                    ),
                    self.PIPELINE_COMPLETED_LOG_MESSAGE,
                    self.ORPHANED_PRODUCT_VALUE_CHECK_LOG_MESSAGE,
                    self.SKIPPED_ITEMS_LOG_MESSAGE,
                    (
                        self.LOGGER_PATH,
                        'ERROR',
                        'Skipped {} with UUID {}. Errors: Wrong {} value for UUID: {},'
                        ' Unable to validate that product exists due to invalid Product Type'
                        .format(
                            INVALID_PRODUCT_VALUE_CSV_DICT['PRODUCT TYPE'].lower(),
                            INVALID_PRODUCT_VALUE_CSV_DICT['UUID'],
                            field_error_name,
                            INVALID_PRODUCT_VALUE_CSV_DICT['UUID'],
                        )
                    ),
                    self.COMPLETED_LOG_MESSAGE,
                )
                assert ProductValue.objects.count() == initial_product_value_obj_count

    @ddt.data('course', 'program')
    def test_missing_product_validation_failure(self, product_type, jwt_decode_patch):  # pylint: disable=unused-argument
        initial_product_value_obj_count = ProductValue.objects.count()
        INVALID_PRODUCT_VALUE_CSV_DICT = {
            **mock_data.VALID_PRODUCT_VALUE_CSV_DICT,
            'PRODUCT TYPE': product_type
        }

        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [INVALID_PRODUCT_VALUE_CSV_DICT])
            with LogCapture(self.LOGGER_PATH) as log_capture:
                loader = ProductValueCSVDataLoader(self.partner, csv_path=csv.name)
                loader.ingest()
                self._assert_default_logs(log_capture)

                log_capture.check_present(
                    self.INITIATED_LOG_MESSAGE,
                    (
                        self.LOGGER_PATH,
                        'ERROR',
                        'Data validation issue for product with UUID: {}.'
                        ' Skipping ingestion for this item.'
                        ' Details: {} with UUID: {} was not found'
                        .format(
                            INVALID_PRODUCT_VALUE_CSV_DICT['UUID'],
                            INVALID_PRODUCT_VALUE_CSV_DICT['PRODUCT TYPE'].capitalize(),
                            INVALID_PRODUCT_VALUE_CSV_DICT['UUID']
                        )
                    ),
                    self.PIPELINE_COMPLETED_LOG_MESSAGE,
                    self.ORPHANED_PRODUCT_VALUE_CHECK_LOG_MESSAGE,
                    self.SKIPPED_ITEMS_LOG_MESSAGE,
                    (
                        self.LOGGER_PATH,
                        'ERROR',
                        'Skipped {} with UUID {}. Errors: {} with UUID: {} was not found'
                        .format(
                            INVALID_PRODUCT_VALUE_CSV_DICT['PRODUCT TYPE'],
                            INVALID_PRODUCT_VALUE_CSV_DICT['UUID'],
                            INVALID_PRODUCT_VALUE_CSV_DICT['PRODUCT TYPE'].capitalize(),
                            INVALID_PRODUCT_VALUE_CSV_DICT['UUID']),
                    ),
                    self.COMPLETED_LOG_MESSAGE,
                )
                assert ProductValue.objects.count() == initial_product_value_obj_count

    def test_uuid_validation_failure(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Verify that data validation fails given an invalid uuid.
        """
        invalid_uuid = 'xyz123'
        initial_product_value_obj_count = ProductValue.objects.count()
        INVALID_PRODUCT_VALUE_CSV_DICT = {
            **mock_data.VALID_PRODUCT_VALUE_CSV_DICT,
            'UUID': invalid_uuid
        }

        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [INVALID_PRODUCT_VALUE_CSV_DICT])
            with LogCapture(self.LOGGER_PATH) as log_capture:
                loader = ProductValueCSVDataLoader(self.partner, csv_path=csv.name)
                loader.ingest()
                self._assert_default_logs(log_capture)

                log_capture.check_present(
                    self.INITIATED_LOG_MESSAGE,
                    (
                        self.LOGGER_PATH,
                        'ERROR',
                        'Data validation issue for product with UUID: {0}.'
                        ' Skipping ingestion for this item.'
                        ' Details: Invalid UUID: {0},'
                        ' Unable to validate that product exists due to invalid UUID'
                        .format(invalid_uuid)
                    ),
                    self.PIPELINE_COMPLETED_LOG_MESSAGE,
                    self.ORPHANED_PRODUCT_VALUE_CHECK_LOG_MESSAGE,
                    self.SKIPPED_ITEMS_LOG_MESSAGE,
                    (
                        self.LOGGER_PATH,
                        'ERROR',
                        'Skipped course with UUID {bad_uuid}. Errors: Invalid UUID: {bad_uuid},'
                        ' Unable to validate that product exists due to invalid UUID'
                        .format(bad_uuid=invalid_uuid)
                    ),
                    self.COMPLETED_LOG_MESSAGE,
                )
                assert ProductValue.objects.count() == initial_product_value_obj_count

    @ddt.data('course', 'program')
    def test_product_success_flow(self, product_type, jwt_decode_patch):  # pylint: disable=unused-argument
        valid_product_value_csv_dict = {
            **mock_data.VALID_PRODUCT_VALUE_CSV_DICT,
            'PRODUCT TYPE': product_type
        }
        valid_uuid = valid_product_value_csv_dict['UUID']

        if product_type == 'program':
            self._setup_program(valid_uuid)
        else:
            self._setup_course(valid_uuid)

        assert ProductValue.objects.count() == 0

        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [valid_product_value_csv_dict])
            with LogCapture(self.LOGGER_PATH) as log_capture:
                loader = ProductValueCSVDataLoader(self.partner, csv_path=csv.name)
                loader.ingest()

                if product_type == 'program':
                    product = Program.objects.get(uuid=valid_uuid)
                else:
                    product = Course.everything.get(draft=False, uuid=valid_uuid)

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
                        "Created product value data for {} with UUID: {}".format(product_type, valid_uuid)
                    ),
                    self.PIPELINE_COMPLETED_LOG_MESSAGE,
                    self.ORPHANED_PRODUCT_VALUE_CHECK_LOG_MESSAGE,
                    (
                        self.LOGGER_PATH,
                        'INFO',
                        'Successfully updated {}s:'.format(product_type)
                    ),
                    (
                        self.LOGGER_PATH,
                        'INFO',
                        "Created product value data for {} with UUID: {}".format(product_type, valid_uuid)
                    ),
                    self.COMPLETED_LOG_MESSAGE,
                )
                assert ProductValue.objects.count() == 1
                product.refresh_from_db()
                assert product.in_year_value == ProductValue.objects.all().first()

    @ddt.data('course', 'program')
    def test_product_success_flow_existing_product_value_orphaned(self, product_type, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Verify that a new Product Value is created and the old one is deleted if orphaned.
        """
        valid_product_value_csv_dict = {
            **mock_data.VALID_PRODUCT_VALUE_CSV_DICT,
            'PRODUCT TYPE': product_type
        }
        valid_uuid = valid_product_value_csv_dict['UUID']

        if product_type == 'course':
            self._setup_course(valid_uuid, True)
        else:
            self._setup_program(valid_uuid, True)

        assert ProductValue.objects.count() == 1
        old_product_value = ProductValue.objects.all().first()

        with NamedTemporaryFile() as csv:
            csv = self._write_csv(
                csv, [valid_product_value_csv_dict]
            )
            with LogCapture(self.LOGGER_PATH) as log_capture:
                loader = ProductValueCSVDataLoader(self.partner, csv_path=csv.name)
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
                        'Updated product value data for {} with UUID: {}'.format(product_type, valid_uuid)
                    ),
                    self.PIPELINE_COMPLETED_LOG_MESSAGE,
                    self.ORPHANED_PRODUCT_VALUE_CHECK_LOG_MESSAGE,
                    (
                        self.LOGGER_PATH,
                        'INFO',
                        'Removed orphaned product value with id: {}'.format(old_product_value.id)
                    ),
                    (
                        self.LOGGER_PATH,
                        'INFO',
                        'Successfully updated {}s:'.format(product_type)
                    ),
                    (
                        self.LOGGER_PATH,
                        'INFO',
                        'Updated product value data for {} with UUID: {}'.format(product_type, valid_uuid)
                    ),
                    self.COMPLETED_LOG_MESSAGE,
                )
                assert ProductValue.objects.count() == 1
                assert old_product_value != ProductValue.objects.all().first()

    @ddt.data(Course, Program)
    def test_product_success_flow_existing_product_value_not_orphaned(self, product_model, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Verify that a new Product Value is created and the old one is not deleted if not orphaned.
        """
        product_type = product_model._meta.model_name
        valid_product_value_csv_dict = {
            **mock_data.VALID_PRODUCT_VALUE_CSV_DICT,
            'PRODUCT TYPE': product_type
        }

        valid_uuid = valid_product_value_csv_dict['UUID']
        original_product_value = self._set_up_product_value()
        self._setup_course_with_product_value(valid_uuid, original_product_value)
        self._setup_program_with_product_value(valid_uuid, original_product_value)

        assert ProductValue.objects.count() == 1

        with NamedTemporaryFile() as csv:
            csv = self._write_csv(
                csv, [valid_product_value_csv_dict]
            )
            with LogCapture(self.LOGGER_PATH) as log_capture:
                loader = ProductValueCSVDataLoader(self.partner, csv_path=csv.name)
                loader.ingest()
                product = product_model.objects.get(uuid=valid_uuid)

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
                        'Updated product value data for {} with UUID: {}'.format(product_type, valid_uuid)
                    ),
                    self.PIPELINE_COMPLETED_LOG_MESSAGE,
                    self.ORPHANED_PRODUCT_VALUE_CHECK_LOG_MESSAGE,
                    (
                        self.LOGGER_PATH,
                        'INFO',
                        'Successfully updated {}s:'.format(product_type)
                    ),
                    (
                        self.LOGGER_PATH,
                        'INFO',
                        'Updated product value data for {} with UUID: {}'.format(product_type, valid_uuid)
                    ),
                    self.COMPLETED_LOG_MESSAGE,
                )
                assert ProductValue.objects.count() == 2
                product.refresh_from_db()
                assert product.in_year_value != original_product_value
