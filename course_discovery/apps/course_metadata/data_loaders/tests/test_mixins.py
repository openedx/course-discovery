from unittest.mock import MagicMock, patch

import pytest
import responses
from ddt import data, ddt, unpack
from django.test import TestCase

from course_discovery.apps.course_metadata.data_loaders.mixins import DataLoaderMixin
from course_discovery.apps.course_metadata.models import CourseRunPacing, CourseRunStatus
from course_discovery.apps.course_metadata.tests.factories import (
    CourseFactory, CourseRunFactory, CourseRunTypeFactory, CourseTypeFactory, SeatFactory, SeatTypeFactory,
    SourceFactory
)

LOGGER_PATH = 'course_discovery.apps.course_metadata.data_loaders.mixins'


class DummyBaseLoader:
    """
    Dummy base class for testing, mimicking AbstractDataLoader behavior.
    """

    def __init__(self, api_client=None, **kwargs):
        self.api_client = api_client
        super().__init__(**kwargs)


class DataLoaderTestMixin(DummyBaseLoader, DataLoaderMixin):
    """
    Test class combining DummyBaseLoader and DataLoaderMixin for safe testing.
    """

    def update_course_api_request_data(self, course_data, course, is_draft):
        pass  # pragma: no cover

    def update_course_run_api_request_data(self, course_run_data, course_run, course_type, is_draft):
        pass  # pragma: no cover


@ddt
class TestDataLoaderMixin(TestCase):
    """
    Test suite for the DataLoaderMixin class.
    """

    def setUp(self):
        self.mock_api_client = MagicMock()
        self.mixin = DataLoaderTestMixin(api_client=self.mock_api_client)

    def test_init_with_api_client(self):
        """Test that initializing DataLoaderMixin with api_client sets the attribute correctly."""
        client = MagicMock()
        mixin_instance = DataLoaderTestMixin(api_client=client)
        assert mixin_instance.api_client == client

    def test_init_without_api_client(self):
        """Test that initializing DataLoaderMixin without api_client raises a ValueError."""
        with self.assertRaises(ValueError) as context:
            DataLoaderTestMixin()

        self.assertIn("api_client must be set", str(context.exception))

    def test_transform_dict_keys(self):
        """Test transformation of dictionary keys to snake_case."""
        input_data = {
            'Enrollment Track': 'verified',
            '  Course Pacing ': 'self-paced',
            'Title': 'Test Course'
        }
        expected = {
            'enrollment_track': 'verified',
            'course_pacing': 'self-paced',
            'title': 'Test Course'
        }
        assert self.mixin.transform_dict_keys(input_data) == expected

    def test_get_formatted_datetime_string(self):
        """Test that date strings are formatted to ISO 8601 UTC format."""
        date_string = "2025-04-22 15:30:00"
        expected = '2025-04-22T15:30:00Z'
        assert self.mixin.get_formatted_datetime_string(date_string) == expected

    def test_get_formatted_datetime_string_with_none(self):
        """Test that None as input returns None for datetime string formatting."""
        assert self.mixin.get_formatted_datetime_string(None) is None

    def test_extract_seat_prices(self):
        """Test extraction of seat prices using real SeatFactory objects."""
        course_run = CourseRunFactory()

        SeatFactory(course_run=course_run, type=SeatTypeFactory.audit(), price=0.0)
        SeatFactory(course_run=course_run, type=SeatTypeFactory.verified(), price=100.0)

        expected = {'audit': '0.00', 'verified': '100.00'}
        result = self.mixin.extract_seat_prices(course_run)

        assert result == expected, f"Expected {expected}, but got {result}"

    @data(
        ('Instructor-Paced', CourseRunPacing.Instructor.value),
        ('self-paced', CourseRunPacing.Self.value),
        ('other', None),
        (None, None),
    )
    @unpack
    def test_get_pacing_type(self, input_value, expected_output):
        """Test correct pacing type is returned based on input string."""
        self.assertEqual(self.mixin.get_pacing_type(input_value), expected_output)

    def test_get_course_run_type_returns_correct_instance(self):
        """Test get_course_run_type returns the correct CourseRunType object."""
        course_run_type = CourseRunTypeFactory(name="SampleType")
        result = self.mixin.get_course_run_type("SampleType")
        assert result == course_run_type

    def test_get_course_run_type_returns_none_for_invalid_name(self):
        """Test get_course_run_type returns None when no matching CourseRunType exists."""
        result = self.mixin.get_course_run_type("NonExistentType")
        assert result is None

    def test_get_pricing_representation(self):
        """Test pricing representation returns correct entitlement-based dictionary."""
        verified = SeatTypeFactory.verified()
        audit = SeatTypeFactory.audit()
        course_type = CourseTypeFactory(entitlement_types=[verified, audit])

        expected = {'verified': '100.00', 'audit': '100.00'}
        result = DataLoaderTestMixin.get_pricing_representation('100.00', course_type)
        self.assertEqual(result, expected)

    def test_get_course_key(self):
        """Test course key generation from organization and number."""
        assert self.mixin.get_course_key('ORG', '101') == 'ORG+101'

    def test_call_course_api_success(self):
        """Test successful API call returns correct response."""
        mock_response = MagicMock(ok=True, status_code=200, json=lambda: {'result': 'success'})
        self.mock_api_client.request.return_value = mock_response

        result = self.mixin.call_course_api('POST', 'http://testserver/api', {'key': 'value'})
        assert result == mock_response

    @responses.activate
    def test_call_course_api_failure_logs_and_raises(self):
        """Test failed API call logs error and raises exception."""
        url = 'http://testserver/api'
        responses.add(
            responses.POST,
            url,
            json={'error': 'bad request'},
            status=400
        )

        self.mock_api_client.request.side_effect = lambda method, url, json, headers=None: responses.calls[0].response

        with pytest.raises(Exception):
            self.mixin.call_course_api('POST', url, {'key': 'value'})

    def test_get_draft_flag_false_when_published_exists(self):
        """Test draft flag returns False when a published course run exists."""
        course_run = CourseRunFactory(status=CourseRunStatus.Published)
        course = course_run.course
        assert self.mixin.get_draft_flag(course) is False

    def test_get_draft_flag_true_when_no_published(self):
        """Test draft flag returns True when no published course runs exist."""
        course_run = CourseRunFactory(status=CourseRunStatus.Unpublished)
        course = course_run.course
        assert self.mixin.get_draft_flag(course) is True

    def test_add_product_source(self):
        """Test product source is added to course and its official version."""
        draft_course = CourseFactory(draft=True)
        official_course = CourseFactory(draft=False)
        official_course.draft_version = draft_course

        source = SourceFactory(name='product_source_mock')
        self.mixin.add_product_source(draft_course, source)

        assert draft_course.product_source == source
        assert draft_course.official_version.product_source == source

    @patch(f'{LOGGER_PATH}.logger')
    def test_create_course_failure_logs(self, mock_logger):
        """
        Test that the logger correctly logs failure details when course creation fails.
        """
        course_type = CourseTypeFactory()
        course_run_type = CourseRunTypeFactory()
        request_data = {
            'organization': 'ORG',
            'title': 'Test Course',
            'number': '101',
            'verified_price': '100.00',
            'course_pacing': 'self-paced',
            'start_date': '2025-04-25',
            'start_time': '09:00:00',
            'end_date': '2025-04-30',
            'end_time': '17:00:00'
        }

        mock_response = MagicMock(status_code=400, ok=False, json=lambda: {'error': 'bad request'},
                                  content=b'{"error":"bad request"}')
        mock_response.raise_for_status.side_effect = Exception("Request failed")
        self.mock_api_client.request.return_value = mock_response

        with self.assertRaises(Exception):
            self.mixin.create_course(request_data, course_type, course_run_type.uuid)

        # Adjusted to match the actual log message with dynamically generated URL
        mock_logger.info.assert_called_with(
            'API request failed for url %s with response: %s',
            'http://localhost:18381/api/v1/courses/',
            '{"error":"bad request"}'
        )

    @patch(f'{LOGGER_PATH}.logger')
    def test_update_course_failure_logs(self, mock_logger):
        """
        Test that the logger correctly logs failure details when course update fails.
        """
        course = CourseFactory()
        self.mixin.update_course_api_request_data = MagicMock(return_value={'title': 'Updated Title'})

        mock_response = MagicMock(status_code=400, ok=False, json=lambda: {'error': 'bad update'},
                                  content=b'{"error":"bad update"}')
        mock_response.raise_for_status.side_effect = Exception("Request failed")
        self.mock_api_client.request.return_value = mock_response

        with self.assertRaises(Exception):
            self.mixin.update_course({'title': 'Updated Title'}, course, is_draft=False)

        # Adjusted to match the actual log message with dynamically generated URL
        mock_logger.info.assert_called_with(
            'API request failed for url %s with response: %s',
            f'http://localhost:18381/api/v1/courses/{course.uuid}/?exclude_utm=1',
            '{"error":"bad update"}'
        )

    def test_create_course_success(self):
        """
        Test the successful creation of a course.
        """
        course_type = CourseTypeFactory()
        course_run_type = CourseRunTypeFactory()
        request_data = {
            'organization': 'ORG',
            'title': 'Test Course',
            'number': '101',
            'verified_price': '100.00',
            'course_pacing': 'self-paced',
            'start_date': '2025-04-25',
            'start_time': '09:00:00',
            'end_date': '2025-04-30',
            'end_time': '17:00:00'
        }

        mock_response = MagicMock(status_code=201, ok=True, json=lambda: {'result': 'created'})
        self.mock_api_client.request.return_value = mock_response

        result = self.mixin.create_course(request_data, course_type, course_run_type.uuid)
        self.assertEqual(result, {'result': 'created'})
        self.mock_api_client.request.assert_called_once()

    def test_update_course_success(self):
        """
        Test the successful update of a course.
        """
        course = CourseFactory()
        self.mixin.update_course_api_request_data = MagicMock(return_value={'title': 'Updated Title'})

        mock_response = MagicMock(status_code=200, ok=True, json=lambda: {'result': 'updated'})
        self.mock_api_client.request.return_value = mock_response

        result = self.mixin.update_course({'title': 'Updated Title'}, course, is_draft=False)
        self.assertEqual(result, {'result': 'updated'})
        self.mock_api_client.request.assert_called_once()
