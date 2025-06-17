"""
Unit tests for CourseRunDataLoader, covering success and failure cases for rerun ingestion.
"""

from tempfile import NamedTemporaryFile
from unittest import mock

import responses
from testfixtures import LogCapture
from ddt import data, ddt

from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase, OAuth2Mixin
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.choices import CourseRunStatus
from course_discovery.apps.course_metadata.data_loaders.course_run_loader import CourseRunDataLoader
from course_discovery.apps.course_metadata.data_loaders.tests.mixins import CSVLoaderMixin
from course_discovery.apps.course_metadata.data_loaders.tests.mock_data import VALID_COURSE_RERUN_DATA
from course_discovery.apps.course_metadata.models import CourseRun, CourseType
from course_discovery.apps.course_metadata.tests.factories import (
    CourseFactory, CourseRunFactory, SeatFactory, SeatTypeFactory, SubjectFactory
)

LOGGER_PATH = 'course_discovery.apps.course_metadata.data_loaders.course_run_loader'


@ddt
@mock.patch(
    'course_discovery.apps.course_metadata.data_loaders.configured_jwt_decode_handler',
    return_value={'preferred_username': 'test_username'}
)
class CourseRunDataLoaderTests(CSVLoaderMixin, OAuth2Mixin, APITestCase):
    """Tests for CourseRunDataLoader ingestion scenarios."""

    rerun_fields = [
        'last_active_run_key', 'start_date', 'start_time',
        'end_date', 'end_time', 'run_type', 'pacing_type', 'move_to_legal_review',
    ]

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
            key_for_reruns='',
            subjects=[SubjectFactory()]  
        )
        self.existing_run = CourseRunFactory(
            course=self.course,
            key=self.COURSE_RUN_KEY,
            status='published',
            draft=True,
            weeks_to_complete=5,
        )
        SeatFactory(course_run=self.existing_run, type=SeatTypeFactory.verified(), price=200.0)

    def mock_call_course_api(self, method, url, payload):
        """Mock requests to the course API using Django test client."""
        if method == 'POST':
            return self.client.post(url, data=payload, format='json')
        elif method == 'PATCH':
            return self.client.patch(url, data=payload, format='json')
        else:
            return None

    def _write_csv(self, csv, lines_dict_list, headers=None):
        """Write course rerun data to CSV."""
        rerun_fields = self.rerun_fields
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
    @data(True, False)
    def test_ingest_legal_review_flag_applied(self, has_publish_date, jwt_decode_patch):  # pylint: disable=unused-argument
        """Verify course run is marked for legal review when flag is true and required data is present."""
        self._setup_prerequisites(self.partner)
        self.mock_studio_calls(self.partner, run_key='course-v1:edx+csv_123+1T2025')

        studio_url = f'{self.partner.studio_url.strip("/")}/api/v1/course_runs/'
        responses.add(responses.POST, f'{studio_url}{self.existing_run.key}/rerun/', status=200)

        data = VALID_COURSE_RERUN_DATA.copy()
        data['move_to_legal_review'] = 'true'

        if has_publish_date:
            data['publish_date'] = '03/01/2025'

        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [data], headers=[*self.rerun_fields, 'publish_date'])
            with mock.patch.object(CourseRunDataLoader, 'call_course_api', self.mock_call_course_api):
                loader = CourseRunDataLoader(self.partner, csv_path=csv.name)
                summary = loader.ingest()['summary']

        run = CourseRun.everything.get(key=summary['new_runs'][0])
        if has_publish_date:
            self.assertEqual(summary['success_count'], 1)
            self.assertEqual(run.status, CourseRunStatus.LegalReview)
            self.assertTrue(run.go_live_date)
        else:
            self.assertEqual(summary['failure_count'], 1)
            self.assertEqual(run.status, CourseRunStatus.Unpublished)
            self.assertIn('The missing data elements are "[\'publish_date\']"', loader.error_logs['MISSING_REQUIRED_DATA'][0])
            self.assertFalse(run.go_live_date)

    @responses.activate
    @data(True, False)
    def test_ingest_change_fields(self, move_to_legal_review, jwt_decode_patch):  # pylint: disable=unused-argument
        """Verify that course run effort and length fields can be changed"""
        self._setup_prerequisites(self.partner)
        self.mock_studio_calls(self.partner, run_key='course-v1:edx+csv_123+1T2025')

        studio_url = f'{self.partner.studio_url.strip("/")}/api/v1/course_runs/'
        responses.add(responses.POST, f'{studio_url}{self.existing_run.key}/rerun/', status=200)

        data = VALID_COURSE_RERUN_DATA.copy()
        if move_to_legal_review:
            data['move_to_legal_review'] = 'true'
            data['publish_date'] = '03/01/2025'

        data['minimum_effort'] = 3
        data['maximum_effort'] = 11
        data['length'] = 7

        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [data], headers=[*self.rerun_fields, 'publish_date', 'minimum_effort', 'maximum_effort', 'length'])
            with mock.patch.object(CourseRunDataLoader, 'call_course_api', self.mock_call_course_api):
                loader = CourseRunDataLoader(self.partner, csv_path=csv.name)
                summary = loader.ingest()['summary']

        run = CourseRun.everything.get(key=summary['new_runs'][0])
        self.assertEqual(run.min_effort, 3)
        self.assertEqual(run.max_effort, 11)
        self.assertEqual(run.weeks_to_complete, 7)
        self.assertNotEqual(run.weeks_to_complete, self.existing_run.weeks_to_complete)

        if move_to_legal_review:
            self.assertEqual(run.status, CourseRunStatus.LegalReview)
        else:
            self.assertEqual(run.status, CourseRunStatus.Unpublished)
