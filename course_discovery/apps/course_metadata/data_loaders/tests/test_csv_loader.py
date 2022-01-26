"""
Unit tests for CSV Data loader.
"""
from tempfile import NamedTemporaryFile
from unittest import mock

import responses
from testfixtures import LogCapture

from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase, OAuth2Mixin
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.data_loaders.csv_loader import CSVDataLoader
from course_discovery.apps.course_metadata.data_loaders.tests import mock_data
from course_discovery.apps.course_metadata.data_loaders.tests.mixins import CSVLoaderMixin
from course_discovery.apps.course_metadata.models import Course, CourseRun
from course_discovery.apps.course_metadata.tests.factories import CourseFactory, CourseRunFactory

LOGGER_PATH = 'course_discovery.apps.course_metadata.data_loaders.csv_loader'


@mock.patch(
    'course_discovery.apps.course_metadata.data_loaders.configured_jwt_decode_handler',
    return_value={'preferred_username': 'test_username'}
)
class TestCSVDataLoader(CSVLoaderMixin, OAuth2Mixin, APITestCase):
    """
    Test Suite for CSVDataLoader.
    """
    def setUp(self) -> None:
        super().setUp()
        self.mock_access_token()
        self.user = UserFactory.create(username="test_user", password=USER_PASSWORD, is_staff=True)
        self.client.login(username=self.user.username, password=USER_PASSWORD)

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

    def _assert_default_logs(self, log_capture):
        """
        Assert the initiation and completion logs are present in the logger.
        """
        log_capture.check_present(
            (
                LOGGER_PATH,
                'INFO',
                'Initiating CSV data loader flow.'
            ),
            (
                LOGGER_PATH,
                'INFO',
                'CSV loader ingest pipeline has completed.'
            )

        )

    def test_missing_organization(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Verify that no course and course run are created for a missing organization in the database.
        """
        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [mock_data.INVALID_ORGANIZATION_DATA])
            with LogCapture(LOGGER_PATH) as log_capture:
                loader = CSVDataLoader(self.partner, csv_path=csv.name)
                loader.ingest()
                self._assert_default_logs(log_capture)
                log_capture.check_present(
                    (
                        LOGGER_PATH,
                        'ERROR',
                        'Organization invalid-organization does not exist in database. Skipping CSV '
                        'loader for course CSV Course'
                    )
                )
                assert Course.objects.count() == 0
                assert CourseRun.objects.count() == 0

    def test_invalid_course_type(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Verify that no course and course run are created for an invalid course track type.
        """
        self._setup_organization(self.partner)
        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [mock_data.INVALID_COURSE_TYPE_DATA])
            with LogCapture(LOGGER_PATH) as log_capture:
                loader = CSVDataLoader(self.partner, csv_path=csv.name)
                loader.ingest()
                self._assert_default_logs(log_capture)
                log_capture.check_present(
                    (
                        LOGGER_PATH,
                        'ERROR',
                        'CourseType invalid track does not exist in the database.'
                    )
                )
                assert Course.objects.count() == 0
                assert CourseRun.objects.count() == 0

    def test_invalid_course_run_type(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Verify that no course and course run are created for an invalid course run track type.
        """
        self._setup_organization(self.partner)
        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [mock_data.INVALID_COURSE_RUN_TYPE_DATA])
            with LogCapture(LOGGER_PATH) as log_capture:
                loader = CSVDataLoader(self.partner, csv_path=csv.name)
                loader.ingest()
                self._assert_default_logs(log_capture)
                log_capture.check_present(
                    (
                        LOGGER_PATH,
                        'ERROR',
                        'CourseRunType invalid track does not exist in the database.'
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
            csv = self._write_csv(csv, [mock_data.VALID_COURSE_AND_COURSE_RUN_CSV_DICT])

            with LogCapture(LOGGER_PATH) as log_capture:
                with mock.patch.object(
                        CSVDataLoader,
                        '_call_course_api',
                        self.mock_call_course_api
                ):
                    loader = CSVDataLoader(self.partner, csv_path=csv.name)
                    loader.ingest()

                    self._assert_default_logs(log_capture)
                    log_capture.check_present(
                        (
                            LOGGER_PATH,
                            'INFO',
                            'Course key edx+csv_123 could not be found in database, creating the course.'
                        )
                    )

                    # Creation call results in creating course and course run objects
                    assert Course.everything.count() == 1
                    assert CourseRun.everything.count() == 1

                    log_capture.check_present(
                        (
                            LOGGER_PATH,
                            'ERROR',
                            'Unexpected error happened while downloading image for course edx+csv_123'
                        )
                    )

    @responses.activate
    def test_single_valid_row(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Verify that for a single row of valid data, both official/non-draft versions
        of course and course runs are created with correct data.
        """
        self._setup_prerequisites(self.partner)
        self.mock_studio_calls(self.partner)
        self.mock_ecommerce_publication(self.partner)
        _, image_content = self.mock_image_response()

        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [mock_data.VALID_COURSE_AND_COURSE_RUN_CSV_DICT])

            with LogCapture(LOGGER_PATH) as log_capture:
                with mock.patch.object(
                        CSVDataLoader,
                        '_call_course_api',
                        self.mock_call_course_api
                ):
                    loader = CSVDataLoader(self.partner, csv_path=csv.name)
                    loader.ingest()

                    self._assert_default_logs(log_capture)
                    log_capture.check_present(
                        (
                            LOGGER_PATH,
                            'INFO',
                            'Course key edx+csv_123 could not be found in database, creating the course.'
                        )
                    )

                    assert Course.objects.count() == 1
                    assert CourseRun.objects.count() == 1

                    course = Course.objects.get(key=self.COURSE_KEY, partner=self.partner)
                    course_run = CourseRun.objects.get(course=course)

                    assert course.image.read() == image_content
                    self._assert_course_data(course, self.BASE_EXPECTED_COURSE_DATA)
                    self._assert_course_run_data(course_run, self.BASE_EXPECTED_COURSE_RUN_DATA)

    @responses.activate
    def test_ingest_flow_for_preexisting_course(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Verify that the loader updates the existing draft versions of the course and its
        associated course run.
        """
        self._setup_prerequisites(self.partner)
        self.mock_studio_calls(self.partner)
        self.mock_ecommerce_publication(self.partner)
        self.mock_image_response()

        course = CourseFactory(key=self.COURSE_KEY, partner=self.partner, type=self.course_type, draft=True)
        CourseRunFactory(
            course=course,
            key=self.COURSE_RUN_KEY,
            type=self.course_run_type,
            draft=True,
        )

        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [mock_data.VALID_COURSE_AND_COURSE_RUN_CSV_DICT])

            with LogCapture(LOGGER_PATH) as log_capture:
                with mock.patch.object(
                        CSVDataLoader,
                        '_call_course_api',
                        self.mock_call_course_api
                ):
                    loader = CSVDataLoader(self.partner, csv_path=csv.name)
                    loader.ingest()

                    self._assert_default_logs(log_capture)
                    log_capture.check_present(
                        (
                            LOGGER_PATH,
                            'INFO',
                            'Course edx+csv_123 is located in the database.'
                        )
                    )

                    course = Course.objects.get(key=self.COURSE_KEY, partner=self.partner)
                    course_run = CourseRun.objects.get(course=course)

                    self._assert_course_data(course, self.BASE_EXPECTED_COURSE_DATA)
                    self._assert_course_run_data(course_run, self.BASE_EXPECTED_COURSE_RUN_DATA)

    @responses.activate
    def test_invalid_language(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Verify that the course run update fails if an invalid language information is provided
        in the data but the course information is updated properly.
        """
        self._setup_prerequisites(self.partner)
        self.mock_studio_calls(self.partner)
        _, image_content = self.mock_image_response()

        expected_course_response = {
            **self.BASE_EXPECTED_COURSE_DATA,
            'draft': True
        }

        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [mock_data.INVALID_LANGUAGE])

            with LogCapture(LOGGER_PATH) as log_capture:
                with mock.patch.object(
                        CSVDataLoader,
                        '_call_course_api',
                        self.mock_call_course_api
                ):
                    loader = CSVDataLoader(self.partner, csv_path=csv.name)
                    loader.ingest()

                    self._assert_default_logs(log_capture)

                    log_capture.check_present(
                        (
                            LOGGER_PATH,
                            'INFO',
                            'Course key edx+csv_123 could not be found in database, creating the course.'
                        )
                    )
                    log_capture.check_present(
                        (
                            LOGGER_PATH,
                            'ERROR',
                            'An unknown error occurred while updating course run information'
                        )
                    )

                    assert Course.everything.count() == 1
                    assert CourseRun.everything.count() == 1

                    course = Course.everything.get(key=self.COURSE_KEY, partner=self.partner)

                    assert course.image.read() == image_content
                    self._assert_course_data(course, expected_course_response)
