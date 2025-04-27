"""
Unit tests for Course Loader.
"""
import copy
import datetime
from decimal import Decimal
from tempfile import NamedTemporaryFile
from unittest import mock

import responses
from ddt import data, ddt, unpack
from edx_toggles.toggles.testutils import override_waffle_switch
from pytz import UTC
from testfixtures import LogCapture

from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase, OAuth2Mixin
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.choices import (
    BulkOperationType, CourseRunStatus, ExternalCourseMarketingType, ExternalProductStatus
)
from course_discovery.apps.course_metadata.data_loaders.constants import CSVIngestionErrorMessages, CSVIngestionErrors
from course_discovery.apps.course_metadata.data_loaders.course_loader import CourseLoader
from course_discovery.apps.course_metadata.data_loaders.tests import mock_data
from course_discovery.apps.course_metadata.data_loaders.tests.mixins import CSVLoaderMixin
from course_discovery.apps.course_metadata.models import Course, CourseRun, CourseType
from course_discovery.apps.course_metadata.tests.factories import CourseFactory, CourseTypeFactory
from course_discovery.apps.course_metadata.toggles import (
    IS_COURSE_RUN_VARIANT_ID_EDITABLE, IS_SUBDIRECTORY_SLUG_FORMAT_ENABLED,
    IS_SUBDIRECTORY_SLUG_FORMAT_FOR_EXEC_ED_ENABLED
)

LOGGER_PATH = 'course_discovery.apps.course_metadata.data_loaders.course_loader'
LOGGER_PATH_MIXIN = 'course_discovery.apps.course_metadata.data_loaders.mixins'


@ddt
@mock.patch(
    'course_discovery.apps.course_metadata.data_loaders.configured_jwt_decode_handler',
    return_value={'preferred_username': 'test_username'}
)
class TestCourseLoader(CSVLoaderMixin, OAuth2Mixin, APITestCase):
    """
    Test Suite for CSVDataLoader.
    """
    def setUp(self) -> None:
        super().setUp()
        self.mock_access_token()
        self.user = UserFactory.create(username="test_user", password=USER_PASSWORD, is_staff=True)
        self.client.login(username=self.user.username, password=USER_PASSWORD)

    def mock_call_course_api(self, method, url, payload):
        """
        Helper method to make api calls using test client.
        """
        response = None
        if method == 'POST':
            response = self.client.post(
                url,
                data=payload,
                format='json'
            )
        elif method == 'PATCH':
            response = self.client.patch(
                url,
                data=payload,
                format='json'
            )
        return response

    def test_course_loader_ingest_for_course_creation(self, mock_jwt_decode_handler):
        """
        Test Course Loader for course creation.
        """
        self._setup_prerequisites(self.partner)
        self.mock_studio_calls(self.partner)
        self.mock_ecommerce_publication(self.partner)

        csv_data = {
            **mock_data.VALID_COURSE_LOADER_COURSE_AND_COURSE_RUN_CREATION_MINIMAL_CSV_DICT,
        }
        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [csv_data], headers=mock_data.COURSE_LOADER_MINIMAL_CSV_HEADERS)
            with LogCapture(LOGGER_PATH) as log_capture:
                with mock.patch.object(
                        CourseLoader,
                        'call_course_api',
                        self.mock_call_course_api
                ):
                    loader = CourseLoader(
                        self.partner, csv_path=csv.name,
                        product_source=self.source.slug,
                        task_type=BulkOperationType.CourseCreate
                    )
                    loader.ingest()
                    log_capture.check_present(
                        (
                            LOGGER_PATH,
                            'INFO',
                            f"Initiating Course Loader for {BulkOperationType.CourseCreate}"
                        )
                    )
                    self.assertEqual(loader.ingestion_summary['success_count'], 1)
                    # Assert the course and course run are created
                    course = Course.everything.get(key=csv_data['organization'] + '+' + csv_data['number'])
                    self.assertEqual(course.title, csv_data['title'])
                    self.assertEqual(course.partner, self.partner)
                    self.assertEqual(course.type, CourseType.objects.get(name=csv_data['course_enrollment_track']))
                    course_run = CourseRun.everything.get(
                        course=course,
                    )
                    self.assertEqual(course_run.status, CourseRunStatus.Unpublished)

    def test_course_loader_ingest_for_course_creation_skip_if_exists(self, mock_jwt_decode_handler):
        """
        Test Course Loader for course creation.
        """
        self._setup_prerequisites(self.partner)
        self.mock_studio_calls(self.partner)
        self.mock_ecommerce_publication(self.partner)

        csv_data = {
            **mock_data.VALID_COURSE_LOADER_COURSE_AND_COURSE_RUN_CREATION_MINIMAL_CSV_DICT,
        }
        CourseFactory.create(
            key=csv_data['organization'] + '+' + csv_data['number'],
            partner=self.partner,
            title=csv_data['title'],
            type=CourseType.objects.get(name=csv_data['course_enrollment_track']),
        )
        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [csv_data], headers=mock_data.COURSE_LOADER_MINIMAL_CSV_HEADERS)
            course_key = csv_data['organization'] + '+' + csv_data['number']
            with LogCapture(LOGGER_PATH) as log_capture:
                with mock.patch.object(
                        CourseLoader,
                        'call_course_api',
                        self.mock_call_course_api
                ):
                    loader = CourseLoader(
                        self.partner, csv_path=csv.name,
                        product_source=self.source.slug,
                        task_type=BulkOperationType.CourseCreate
                    )
                    loader.ingest()
                    log_capture.check_present(
                        (
                            LOGGER_PATH,
                            'INFO',
                            f"Initiating Course Loader for {BulkOperationType.CourseCreate}"
                        ),
                        (
                            LOGGER_PATH,
                            'WARNING',
                            f'Course with key {course_key} already exists. Skipping creation.'
                        )
                    )
                    self.assertEqual(loader.ingestion_summary['success_count'], 0)

    def test_course_loader_ingest_for_course_creation_with_attributes_required_for_review(self, mock_jwt_decode_handler):
        """
        Test Course Loader for course creation.
        """
        self._setup_prerequisites(self.partner)
        self.mock_studio_calls(self.partner)
        self.mock_ecommerce_publication(self.partner)
        self.mock_image_response()

        csv_data = {
            **mock_data.VALID_COURSE_LOADER_COURSE_AND_COURSE_RUN_CREATION_CSV_DICT,
        }
        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [csv_data], headers=mock_data.COURSE_LOADER_CSV_HEADERS)
            with LogCapture(LOGGER_PATH) as log_capture:
                with mock.patch.object(
                        CourseLoader,
                        'call_course_api',
                        self.mock_call_course_api
                ):
                    loader = CourseLoader(
                        self.partner, csv_path=csv.name,
                        product_source=self.source.slug,
                        task_type=BulkOperationType.CourseCreate
                    )
                    loader.ingest()
                    log_capture.check_present(
                        (
                            LOGGER_PATH,
                            'INFO',
                            f"Initiating Course Loader for {BulkOperationType.CourseCreate}"
                        )
                    )
                    self.assertEqual(loader.ingestion_summary['success_count'], 1)
                    # Assert the course and course run are created
                    course = Course.everything.get(key=csv_data['Organization'] + '+' + csv_data['Number'])
                    self.assertEqual(course.title, csv_data['Title'])
                    self.assertEqual(course.partner, self.partner)
                    self.assertEqual(course.type, CourseType.objects.get(name=csv_data['Course Enrollment Track']))
                    course_run = CourseRun.everything.get(
                        course=course,
                    )
                    self.assertEqual(course_run.status, CourseRunStatus.LegalReview)

    @data(
        (
            'Audit Only',
            CourseType.AUDIT,
            {},
            [],
        ),
        (
            'Masters Only',
            'masters',
            {
                'Long Description',
                'Short Description',
                'What you will Learn',
            },
            ['Long Description', 'Short Description', 'What you will Learn'],
        ),
    )
    @unpack
    def test_course_loader__validate_course_data__course_types(
        self, course_type_name, course_type_slug, fields_to_remove, headers_to_remove, mock_jwt_decode_handler
    ):
        """
        Test validate_course_data logic for various course types.
        """
        self._setup_prerequisites(self.partner)
        CourseTypeFactory(name=course_type_name, slug=course_type_slug)

        csv_data = {
            **mock_data.VALID_COURSE_LOADER_COURSE_AND_COURSE_RUN_CREATION_CSV_DICT,
            'Course Enrollment Track': course_type_name,
            'Course Run Enrollment Track': course_type_name,
        }

        for field in fields_to_remove:
            csv_data.pop(field)

        csv_headers = copy.deepcopy(mock_data.COURSE_LOADER_CSV_HEADERS)
        for field in headers_to_remove:
            csv_headers.remove(field)

        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [csv_data], headers=csv_headers)
            loader = CourseLoader(
                self.partner, csv_path=csv.name,
                product_source=self.source.slug,
                task_type=BulkOperationType.CourseCreate
            )
            row = loader.transform_dict_keys(csv_data)
            missing_field = loader.validate_course_data(
                CourseType.objects.get(name=course_type_name),
                row
            )
            assert missing_field == ''

    def test_course_loader__validate_course_data__returns_missing_fields_string(self, mock_jwt_decode_handler):
        """
        Test validate_course_data returns missing fields string when required fields are missing.
        """
        self._setup_prerequisites(self.partner)
        CourseTypeFactory(name='Masters Only', slug='masters')

        # Start from the full valid CSV dict
        csv_data = copy.deepcopy(mock_data.VALID_COURSE_LOADER_COURSE_AND_COURSE_RUN_CREATION_CSV_DICT)
        csv_data.update({
            'Course Enrollment Track': 'Masters Only',
            'Course Run Enrollment Track': 'Masters Only',
            'Move to Legal Review': 'True',
        })

        fields_to_remove = [
            'Image', 'Level Type', 'Primary Subject', 'Publish Date',
            'Minimum Effort', 'Maximum Effort', 'Length'
        ]
        for field in fields_to_remove:
            csv_data.pop(field, None)

        csv_headers = [header for header in mock_data.COURSE_LOADER_CSV_HEADERS if header not in fields_to_remove]

        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [csv_data], headers=csv_headers)
            loader = CourseLoader(
                self.partner, csv_path=csv.name,
                product_source=self.source.slug,
                task_type=BulkOperationType.CourseCreate
            )
            row = loader.transform_dict_keys(csv_data)
            course_type = CourseType.objects.get(slug='masters')
            missing_fields = loader.validate_course_data(course_type, row)

            # Validate returned missing fields
            for expected_missing in ['image', 'level_type', 'primary_subject', 'publish_date', 'minimum_effort', 'maximum_effort', 'length']:
                self.assertIn(expected_missing, missing_fields)

            # Also check it returns a non-empty string
            self.assertIsInstance(missing_fields, str)
            self.assertNotEqual(missing_fields, '')

    def test_missing_organization(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Verify that no course and course run are created for a missing organization in the database.
        """
        csv_data = copy.deepcopy(mock_data.VALID_COURSE_LOADER_COURSE_AND_COURSE_RUN_CREATION_CSV_DICT)
        csv_data.update({
            'Organization': 'invalid-organization',
        })
        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [csv_data], headers=mock_data.COURSE_LOADER_CSV_HEADERS)
            with LogCapture(LOGGER_PATH) as log_capture:
                with LogCapture(LOGGER_PATH_MIXIN) as log_capture_mixin:
                    loader = CourseLoader(
                    self.partner, csv_path=csv.name,
                    product_source=self.source.slug,
                    task_type=BulkOperationType.CourseCreate
                )
                    loader.ingest()
                    log_capture_mixin.check_present(
                        (
                            LOGGER_PATH_MIXIN,
                            'ERROR',
                            '[MISSING_ORGANIZATION] Unable to locate partner organization with key invalid-organization '
                            'for the course titled Intro to Course Loader.'
                        )
                    )
                    assert Course.objects.count() == 0
                    assert CourseRun.objects.count() == 0
    
    def test_invalid_course_type(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Verify that no course and course run are created for an invalid course track type.
        """
        self._setup_organization(self.partner)
        csv_data = copy.deepcopy(mock_data.VALID_COURSE_LOADER_COURSE_AND_COURSE_RUN_CREATION_CSV_DICT)
        csv_data.update({
            'Course Enrollment Track': 'invalid track',
        })
        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [csv_data], headers=mock_data.COURSE_LOADER_CSV_HEADERS)
            with LogCapture(LOGGER_PATH) as log_capture:
                with LogCapture(LOGGER_PATH_MIXIN) as log_capture_mixin:
                    loader = CourseLoader(
                        self.partner, csv_path=csv.name,
                        product_source=self.source.slug,
                        task_type=BulkOperationType.CourseCreate
                    )
                    loader.ingest()
                    log_capture_mixin.check_present(
                        (
                            LOGGER_PATH_MIXIN,
                            'ERROR',
                            '[MISSING_COURSE_TYPE] Unable to find the course enrollment track "invalid track"'
                            ' for the course Intro to Course Loader'
                        )
                    )
                    assert Course.objects.count() == 0
                    assert CourseRun.objects.count() == 0

    @responses.activate
    def test_image_download_failure(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Verify that if the course image download fails, the ingestion does not complete.
        """
        self._setup_prerequisites(self.partner)
        self.mock_studio_calls(self.partner)
        self.mock_ecommerce_publication(self.partner)
        responses.add(
            responses.GET,
            'https://example.com/image.jpg',
            status=400,
            body='Image unavailable',
            content_type='image/jpeg',
        )

        with NamedTemporaryFile() as csv:
            csv = self._write_csv(
                csv,
                [mock_data.VALID_COURSE_LOADER_COURSE_AND_COURSE_RUN_CREATION_CSV_DICT],
                headers=mock_data.COURSE_LOADER_CSV_HEADERS
            )

            with LogCapture(LOGGER_PATH) as log_capture:
                with LogCapture(LOGGER_PATH_MIXIN) as log_capture_mixin:
                    with mock.patch.object(
                            CourseLoader,
                            'call_course_api',
                            self.mock_call_course_api
                    ):
                        loader = CourseLoader(
                            self.partner, csv_path=csv.name,
                            product_source=self.source.slug,
                            task_type=BulkOperationType.CourseCreate
                        )
                        loader.ingest()

                        # Creation call results in creating course and course run objects
                        assert Course.everything.count() == 1
                        assert CourseRun.everything.count() == 1

                        log_capture_mixin.check_present(
                            (
                                LOGGER_PATH_MIXIN,
                                'ERROR',
                                '[IMAGE_DOWNLOAD_FAILURE] The course image download failed for the course Intro to Course Loader.'
                            )
                        )
