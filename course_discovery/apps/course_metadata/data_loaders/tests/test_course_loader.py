"""
Unit tests for Course Loader.
"""
import copy
from tempfile import NamedTemporaryFile
from unittest import mock

import responses
from ddt import data, ddt, unpack
from testfixtures import LogCapture

from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase, OAuth2Mixin
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.choices import BulkOperationType, CourseRunStatus
from course_discovery.apps.course_metadata.data_loaders.constants import CSVIngestionErrorMessages, CSVIngestionErrors
from course_discovery.apps.course_metadata.data_loaders.course_loader import CourseLoader
from course_discovery.apps.course_metadata.data_loaders.tests import mock_data
from course_discovery.apps.course_metadata.data_loaders.tests.mixins import CSVLoaderMixin
from course_discovery.apps.course_metadata.data_loaders.tests.test_utils import MockExceptionWithResponse
from course_discovery.apps.course_metadata.models import Course, CourseRun, CourseRunType, CourseType
from course_discovery.apps.course_metadata.tests.factories import CourseFactory, CourseRunFactory, CourseTypeFactory

LOGGER_PATH = 'course_discovery.apps.course_metadata.data_loaders.course_loader'
MIXIN_LOGGER_PATH = 'course_discovery.apps.course_metadata.data_loaders.mixins'


@ddt
@mock.patch(
    'course_discovery.apps.course_metadata.data_loaders.configured_jwt_decode_handler',
    return_value={'preferred_username': 'test_username'}
)
class TestCourseLoader(CSVLoaderMixin, OAuth2Mixin, APITestCase):
    """
    Test Suite for CourseLoader.
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

    def test_course_loader_ingest_for_course_creation(self, mock_jwt_decode_handler):  # pylint: disable=unused-argument
        """
        Test Course Loader for course creation.
        """
        self._setup_prerequisites(self.partner)
        self.mock_studio_calls(self.partner)
        self.mock_ecommerce_publication(self.partner)

        csv_data = {
            **mock_data.MINIMAL_VALID_COURSE_LOADER_COURSE_AND_COURSE_RUN_CREATION_CSV_DICT,
        }
        with NamedTemporaryFile() as csv:
            csv = self._write_csv(
                csv, [csv_data],
                headers=mock_data.MINIMAL_VALID_COURSE_LOADER_COURSE_AND_COURSE_RUN_CREATION_CSV_DICT.keys()
            )
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
                    course = Course.everything.get(key=f"{csv_data['Organization']}+{csv_data['Number']}")
                    self.assertEqual(course.title, csv_data['Title'])
                    self.assertEqual(course.partner, self.partner)
                    self.assertEqual(course.type, CourseType.objects.get(name=csv_data['Course Enrollment Track']))
                    course_run = CourseRun.everything.get(
                        course=course,
                    )
                    self.assertEqual(course_run.status, CourseRunStatus.Unpublished)

    def test_course_loader_ingest_for_course_creation_skip_if_exists(self, mock_jwt_decode_handler):  # pylint: disable=unused-argument
        """
        Test Course Loader for course creation.
        """
        self._setup_prerequisites(self.partner)
        self.mock_studio_calls(self.partner)
        self.mock_ecommerce_publication(self.partner)
        _ = self.mock_image_response()

        csv_data = {
            **mock_data.VALID_COURSE_LOADER_COURSE_AND_COURSE_RUN_CREATION_CSV_DICT,
        }
        course = CourseFactory.create(
            key=f"{csv_data['Organization']}+{csv_data['Number']}",
            partner=self.partner,
            title=csv_data['Title'],
            type=CourseType.objects.get(name=csv_data['Course Enrollment Track']),
        )
        CourseRunFactory.create(
            course=course,
            draft=True,
            pacing_type=csv_data['Course Pacing'],
            type=CourseRunType.objects.get(name=csv_data['Course Run Enrollment Track']),
        )
        with NamedTemporaryFile() as csv:
            csv = self._write_csv(
                csv, [csv_data],
                headers=mock_data.VALID_COURSE_LOADER_COURSE_AND_COURSE_RUN_CREATION_CSV_DICT.keys()
            )
            course_key = f"{csv_data['Organization']}+{csv_data['Number']}"
            with LogCapture(LOGGER_PATH) as log_capture:
                with mock.patch.object(CourseLoader, "call_course_api", self.mock_call_course_api), mock.patch.object(
                    CourseLoader, "create_course"
                ) as mock_create_course:
                    loader = CourseLoader(
                        self.partner, csv_path=csv.name,
                        product_source=self.source.slug,
                        task_type=BulkOperationType.CourseCreate
                    )
                    loader.ingest()
                    mock_create_course.assert_not_called()
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
                    self.assertEqual(loader.ingestion_summary['others'], [
                        f'Course with key {course_key} already exists. Skipping creation.'
                    ])
                    self.assertEqual(loader.ingestion_summary['success_count'], 1)

    def test_course_loader_ingest_for_course_creation_with_attributes_required_for_review(
        self, mock_jwt_decode_handler
    ):  # pylint: disable=unused-argument
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
            csv = self._write_csv(
                csv, [csv_data],
                headers=mock_data.VALID_COURSE_LOADER_COURSE_AND_COURSE_RUN_CREATION_CSV_DICT.keys()
            )
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
                    course = Course.everything.get(key=f"{csv_data['Organization']}+{csv_data['Number']}")
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
                'What will you Learn',
            },
            ['Long Description', 'Short Description', 'What will you Learn'],
        ),
    )
    @unpack
    def test_course_loader__validate_course_data__course_types(
        self, course_type_name, course_type_slug, fields_to_remove, headers_to_remove, mock_jwt_decode_handler
    ):  # pylint: disable=unused-argument
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

        csv_headers = list(mock_data.VALID_COURSE_LOADER_COURSE_AND_COURSE_RUN_CREATION_CSV_DICT.keys())
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

    def test_course_loader__validate_course_data__returns_missing_fields_string(self, mock_jwt_decode_handler):  # pylint: disable=unused-argument
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

        csv_headers = [
            header for header in mock_data.VALID_COURSE_LOADER_COURSE_AND_COURSE_RUN_CREATION_CSV_DICT
            if header not in fields_to_remove
        ]

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
            for expected_missing in [
                "image",
                "level_type",
                "primary_subject",
                "publish_date",
                "minimum_effort",
                "maximum_effort",
                "length",
            ]:
                self.assertIn(expected_missing, missing_fields)

    def test_validating_course_data(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Verify that no course and course run are created for a missing organization in the database.
        """
        csv_data = copy.deepcopy(mock_data.VALID_COURSE_LOADER_COURSE_AND_COURSE_RUN_CREATION_CSV_DICT)
        csv_data.update({
            'Organization': 'invalid-organization',
        })
        with NamedTemporaryFile() as csv:
            csv = self._write_csv(
                csv, [csv_data],
                headers=mock_data.VALID_COURSE_LOADER_COURSE_AND_COURSE_RUN_CREATION_CSV_DICT.keys(),
            )
            with LogCapture(MIXIN_LOGGER_PATH) as log_capture_mixin:
                loader = CourseLoader(
                    self.partner, csv_path=csv.name,
                    product_source=self.source.slug, task_type=BulkOperationType.CourseCreate
                )
                loader.ingest()
                log_capture_mixin.check_present(
                    (
                        MIXIN_LOGGER_PATH,
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
            csv = self._write_csv(
                csv, [csv_data],
                headers=mock_data.VALID_COURSE_LOADER_COURSE_AND_COURSE_RUN_CREATION_CSV_DICT.keys()
            )
            with LogCapture(MIXIN_LOGGER_PATH) as log_capture_mixin:
                loader = CourseLoader(
                    self.partner, csv_path=csv.name,
                    product_source=self.source.slug,
                    task_type=BulkOperationType.CourseCreate
                )
                loader.ingest()
                log_capture_mixin.check_present(
                    (
                        MIXIN_LOGGER_PATH,
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
                headers=mock_data.VALID_COURSE_LOADER_COURSE_AND_COURSE_RUN_CREATION_CSV_DICT.keys()
            )

            with LogCapture(MIXIN_LOGGER_PATH) as log_capture_mixin:
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
                    self.assertEqual(Course.everything.count(), 1)
                    self.assertEqual(CourseRun.everything.count(), 1)

                    log_capture_mixin.check_present(
                        (
                            MIXIN_LOGGER_PATH,
                            'ERROR',
                            # pylint: disable=line-too-long
                            '[IMAGE_DOWNLOAD_FAILURE] The course image download failed for the course Intro to Course Loader.'
                        )
                    )

    @data(
        {
            "task_type": BulkOperationType.CourseCreate,
            "method_to_mock": "create_course",
            "error_type": CSVIngestionErrors.COURSE_CREATE_ERROR,
            "error_message_template": CSVIngestionErrorMessages.COURSE_CREATE_ERROR,
            "exception_msg": "Create course error",
            "expected_course_count": 0,
            "expected_course_run_count": 0,
        },
        {
            "task_type": BulkOperationType.CourseCreate,
            "method_to_mock": "update_course",
            "error_type": CSVIngestionErrors.COURSE_UPDATE_ERROR,
            "error_message_template": CSVIngestionErrorMessages.COURSE_UPDATE_ERROR,
            "exception_msg": "Update course error",
            "expected_course_count": 1,
            "expected_course_run_count": 1,
        }
    )
    @responses.activate
    def test_exception_flow_for_course_methods(self, config, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Verify that course ingestion fails properly when an exception is raised during course create/update.
        """
        self._setup_prerequisites(self.partner)
        self.mock_studio_calls(self.partner)
        _ = self.mock_image_response()

        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [mock_data.VALID_COURSE_AND_COURSE_RUN_CSV_DICT])

            with mock.patch.object(CourseLoader, "call_course_api", self.mock_call_course_api):
                loader = CourseLoader(
                    self.partner,
                    csv_path=csv.name,
                    product_source=self.source.slug,
                    task_type=config["task_type"]
                )
                loader.register_ingestion_error = mock.MagicMock()
                method_mock = mock.MagicMock()
                setattr(loader, config["method_to_mock"], method_mock)
                method_mock.side_effect = MockExceptionWithResponse(config["exception_msg"].encode())

                with LogCapture(LOGGER_PATH):
                    loader.ingest()

                    expected_error_message = config["error_message_template"].format(
                        course_title=mock_data.VALID_COURSE_AND_COURSE_RUN_CSV_DICT["title"],
                        exception_message=config["exception_msg"]
                    )

                    loader.register_ingestion_error.assert_called_once_with(
                        config["error_type"], expected_error_message
                    )
                    self.assertEqual(Course.everything.count(), config["expected_course_count"])
                    self.assertEqual(CourseRun.everything.count(), config["expected_course_run_count"])

                loader.register_ingestion_error.reset_mock()
                method_mock.reset_mock()
                method_mock.side_effect = None

    @responses.activate
    def test_exception_flow_for_course_run_update_method(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Verify that the course update fails if an exception is raised while updating the course run.
        """
        self._setup_prerequisites(self.partner)
        self.mock_studio_calls(self.partner)
        _ = self.mock_image_response()

        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [mock_data.VALID_COURSE_AND_COURSE_RUN_CSV_DICT])

            with mock.patch.object(
                CourseLoader, "call_course_api", self.mock_call_course_api
            ):
                loader = CourseLoader(
                    self.partner, csv_path=csv.name,
                    product_source=self.source.slug,
                    task_type=BulkOperationType.CourseCreate
                )
                loader.register_ingestion_error = mock.MagicMock()
                loader.update_course_run = mock.MagicMock()

                loader.update_course_run.side_effect = MockExceptionWithResponse(b"Update course run error")

                with LogCapture(LOGGER_PATH):
                    loader.ingest()

                    expected_error_message = CSVIngestionErrorMessages.COURSE_RUN_UPDATE_ERROR.format(
                        course_title=mock_data.VALID_COURSE_AND_COURSE_RUN_CSV_DICT["title"],
                        exception_message="Update course run error",
                    )
                    loader.register_ingestion_error.assert_called_once_with(
                        CSVIngestionErrors.COURSE_RUN_UPDATE_ERROR, expected_error_message
                    )

                loader.register_ingestion_error.reset_mock()
                loader.update_course_run.reset_mock()
                loader.update_course_run.side_effect = None
                loader.register_ingestion_error.side_effect = None
