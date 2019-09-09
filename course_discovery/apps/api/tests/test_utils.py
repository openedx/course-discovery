import ddt
import mock
from django.test import TestCase
from opaque_keys.edx.keys import CourseKey
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from course_discovery.apps.api.utils import StudioAPI, cast2int, get_query_param
from course_discovery.apps.core.utils import serialize_datetime
from course_discovery.apps.course_metadata.tests.factories import CourseRunFactory

LOGGER_PATH = 'course_discovery.apps.api.utils.logger.exception'


@ddt.ddt
class Cast2IntTests(TestCase):
    name = 'foo'

    @ddt.data(
        ('0', 0),
        ('1', 1),
        (None, None),
    )
    @ddt.unpack
    def test_cast_success(self, value, expected):
        self.assertEqual(cast2int(value, self.name), expected)

    @ddt.data('beep', '1.1')
    def test_cast_failure(self, value):
        with mock.patch(LOGGER_PATH) as mock_logger:
            with self.assertRaises(ValueError):
                cast2int(value, self.name)

        self.assertTrue(mock_logger.called)


class TestGetQueryParam:
    def test_with_request(self):
        factory = APIRequestFactory()
        request = Request(factory.get('/?q=1'))

        assert get_query_param(request, 'q') == 1

    def test_without_request(self):
        assert get_query_param(None, 'q') is None


class StudioAPITests(TestCase):
    def setUp(self):
        super().setUp()
        self.client = mock.Mock()
        self.api = StudioAPI(self.client)

    def make_studio_data(self, run, add_pacing=True, add_schedule=True):
        key = CourseKey.from_string(run.key)
        data = {
            'title': run.title,
            'org': key.org,
            'number': key.course,
            'run': key.run,
            'team': [],
        }
        if add_pacing:
            data['pacing_type'] = run.pacing_type
        if add_schedule:
            data['schedule'] = {
                'start': serialize_datetime(run.start),
                'end': serialize_datetime(run.end),
            }
        return data

    def test_create_rerun(self):
        run1 = CourseRunFactory()
        run2 = CourseRunFactory(course=run1.course)
        self.api.create_course_rerun_in_studio(run2, run1.key)

        expected_data = self.make_studio_data(run2)
        self.assertEqual(self.client.course_runs.call_args_list, [mock.call(run1.key)])
        self.assertEqual(self.client.course_runs.return_value.rerun.post.call_args_list[0][0][0], expected_data)

    def test_create_run(self):
        run = CourseRunFactory()
        self.api.create_course_run_in_studio(run)

        expected_data = self.make_studio_data(run)
        self.assertEqual(self.client.course_runs.post.call_args_list[0][0][0], expected_data)

    def test_update_run(self):
        run = CourseRunFactory()
        self.api.update_course_run_details_in_studio(run)

        expected_data = self.make_studio_data(run, add_pacing=False, add_schedule=False)
        self.assertEqual(self.client.course_runs.call_args_list, [mock.call(run.key)])
        self.assertEqual(self.client.course_runs.return_value.patch.call_args_list[0][0][0], expected_data)
