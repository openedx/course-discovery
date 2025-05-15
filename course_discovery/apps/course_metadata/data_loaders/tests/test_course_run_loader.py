"""
Unit tests for CourseRunDataLoader, covering success and failure cases for rerun ingestion.
"""

from tempfile import NamedTemporaryFile
from unittest import mock

import responses
from testfixtures import LogCapture

from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase, OAuth2Mixin
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.choices import CourseRunStatus
from course_discovery.apps.course_metadata.data_loaders.course_run_loader import CourseRunDataLoader
from course_discovery.apps.course_metadata.data_loaders.tests.mixins import CSVLoaderMixin
from course_discovery.apps.course_metadata.data_loaders.tests.mock_data import VALID_COURSE_RERUN_DATA
from course_discovery.apps.course_metadata.models import CourseRun, CourseType
from course_discovery.apps.course_metadata.tests.factories import (
    CourseFactory, CourseRunFactory, SeatFactory, SeatTypeFactory
)

LOGGER_PATH = 'course_discovery.apps.course_metadata.data_loaders.course_run_loader'


@mock.patch(
    'course_discovery.apps.course_metadata.data_loaders.configured_jwt_decode_handler',
    return_value={'preferred_username': 'test_username'}
)
class CourseRunDataLoaderTests(CSVLoaderMixin, OAuth2Mixin, APITestCase):
    """Tests for CourseRunDataLoader ingestion scenarios."""

    def setUp(self):
        """Set up a test user, partner course, course run, and seat."""
        super().setUp()
        self.mock_access_token()
        self.user = UserFactory.create(username="test_user", password=USER_PASSWORD, is_staff=True)
        self.client.login(username=self.user.username, password=USER_PASSWORD)

        self.course = CourseFactory(
            key=self.COURSE_KEY,
            partner=self.partner,
            type=CourseType.objects.get(slug=CourseType.VERIFIED_AUDIT),
            draft=True,
            key_for_reruns=''
        )
        self.existing_run = CourseRunFactory(
            course=self.course,
            key=self.COURSE_RUN_KEY,
            status='published',
            draft=True,
        )
        SeatFactory(course_run=self.existing_run, type=SeatTypeFactory.verified(), price=200.0)

    def mock_call_course_api(self, method, url, payload):
        """Mock POST requests to the course API using Django test client."""
        return self.client.post(url, data=payload, format='json') if method == 'POST' else None

    def _write_csv(self, csv, lines_dict_list, headers=None):
        """Write course rerun data to CSV."""
        rerun_fields = [
            'last_active_run_key', 'start_date', 'start_time',
            'end_date', 'end_time', 'run_type', 'pacing_type', 'move_to_legal_review',
        ]
        headers = headers or rerun_fields
        header_line = ','.join(key.replace('_', ' ').title() for key in headers) + '\n'
        csv.write(header_line.encode())
        for line_dict in lines_dict_list:
            row = ','.join(f'"{line_dict.get(key, "")}"' for key in headers) + '\n'
            csv.write(row.encode())
        csv.seek(0)
        return csv

    @responses.activate
    def test_ingest_successful_course_run_creation(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """Verify rerun is created when ingestion is successful."""
        self._setup_prerequisites(self.partner)
        self.mock_studio_calls(self.partner)

        studio_url = f'{self.partner.studio_url.strip("/")}/api/v1/course_runs/'
        responses.add(responses.POST, f'{studio_url}{self.existing_run.key}/rerun/', status=200)

        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [VALID_COURSE_RERUN_DATA])
            with LogCapture(LOGGER_PATH) as log_capture:
                with mock.patch.object(CourseRunDataLoader, 'call_course_api', self.mock_call_course_api):
                    loader = CourseRunDataLoader(self.partner, csv_path=csv.name)
                    summary = loader.ingest()['summary']

                expected_log_msg = (f'[Row 1] Successfully created rerun course-v1:edx+csv_123+1T2025 '
                                    f'for course: {self.course.title}')

                log_capture.check_present(
                    ('course_discovery.apps.course_metadata.data_loaders.course_run_loader', 'INFO', expected_log_msg)
                )

        self.assertEqual(summary['success_count'], 1)
        self.assertEqual(summary['failure_count'], 0)
        assert CourseRun.everything.filter(key=summary['new_runs'][0]).exists()

    @responses.activate
    def test_ingest_missing_required_fields(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """Fail ingestion when required CSV fields are missing."""
        invalid_data = VALID_COURSE_RERUN_DATA.copy()
        del invalid_data['start_date']

        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [invalid_data])
            with LogCapture(LOGGER_PATH) as log_capture:
                with mock.patch.object(CourseRunDataLoader, 'call_course_api', self.mock_call_course_api):
                    loader = CourseRunDataLoader(self.partner, csv_path=csv.name)
                    summary = loader.ingest()['summary']

                log_capture.check_present(
                    ('course_discovery.apps.course_metadata.data_loaders.course_run_loader', 'ERROR',
                     '[Row 1] Missing required field(s) for course run: course-v1:edx+csv_123+1T2020. '
                     'The missing data elements are: start_date')
                )

        self.assertEqual(summary['success_count'], 0)
        self.assertEqual(summary['failure_count'], 1)

    @responses.activate
    def test_ingest_course_run_not_found(self, jwt_decode_patch):  # pylint: disable=unused-argument
        self.existing_run.delete()

        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [VALID_COURSE_RERUN_DATA])
            with LogCapture(LOGGER_PATH) as log_capture:
                with mock.patch.object(CourseRunDataLoader, 'call_course_api', self.mock_call_course_api):
                    loader = CourseRunDataLoader(self.partner, csv_path=csv.name)
                    summary = loader.ingest()['summary']

            expected_msg_fragment = ("[Row 1] Last Active Course Run with key 'course-v1:edx+csv_123+1T2020' not "
                                     "found. Skipping row.")
            log_capture.check_present(
                (LOGGER_PATH, 'ERROR', expected_msg_fragment)
            )

        self.assertEqual(summary['success_count'], 0)
        self.assertEqual(summary['failure_count'], 1)

    @responses.activate
    def test_ingest_rerun_creation_failure(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """Log error and fail ingestion if rerun creation returns 500."""
        self._setup_prerequisites(self.partner)
        self.mock_studio_calls(self.partner)

        studio_url = f'{self.partner.studio_url.strip("/")}/api/v1/course_runs/'
        responses.add(responses.POST, f'{studio_url}{self.existing_run.key}/rerun/', status=500)

        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [VALID_COURSE_RERUN_DATA])
            with LogCapture(LOGGER_PATH) as log_capture:
                with mock.patch.object(CourseRunDataLoader, 'call_course_api', self.mock_call_course_api):
                    loader = CourseRunDataLoader(self.partner, csv_path=csv.name)
                    summary = loader.ingest()['summary']

                error_logs = [
                    entry for entry in log_capture.actual()
                    if entry[0] == LOGGER_PATH and entry[1] == 'ERROR' and entry[2].startswith(
                        f"[Row 1] Error creating rerun for course '{self.course.title}':"
                    )
                ]
                self.assertTrue(error_logs, "Expected ERROR log about rerun creation failure not found.")

        self.assertEqual(summary['success_count'], 0)
        self.assertEqual(summary['failure_count'], 1)

    @responses.activate
    def test_ingest_legal_review_flag_applied(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """Verify course run is marked for legal review when flag is true."""
        self._setup_prerequisites(self.partner)
        self.mock_studio_calls(self.partner)

        studio_url = f'{self.partner.studio_url.strip("/")}/api/v1/course_runs/'
        responses.add(responses.POST, f'{studio_url}{self.existing_run.key}/rerun/', status=200)

        data = VALID_COURSE_RERUN_DATA.copy()
        data['move_to_legal_review'] = 'true'

        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [data])
            with mock.patch.object(CourseRunDataLoader, 'call_course_api', self.mock_call_course_api):
                loader = CourseRunDataLoader(self.partner, csv_path=csv.name)
                summary = loader.ingest()['summary']

        self.assertEqual(summary['success_count'], 1)
        run = CourseRun.everything.get(key=summary['new_runs'][0])
        self.assertEqual(run.status, CourseRunStatus.LegalReview)
