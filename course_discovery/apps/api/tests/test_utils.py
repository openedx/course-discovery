import datetime
from itertools import product
from unittest import mock

import ddt
from django.test import TestCase
from opaque_keys.edx.keys import CourseKey
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from course_discovery.apps.api.utils import StudioAPI, cast2int, get_query_param
from course_discovery.apps.core.utils import serialize_datetime
from course_discovery.apps.course_metadata.tests.factories import CourseEditorFactory, CourseRunFactory

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


@ddt.ddt
class StudioAPITests(TestCase):
    def setUp(self):
        super().setUp()
        self.client = mock.Mock()
        self.api = StudioAPI(self.client)

    def make_studio_data(self, run, add_pacing=True, add_schedule=True, team=None):
        key = CourseKey.from_string(run.key)
        data = {
            'title': run.title,
            'org': key.org,
            'number': key.course,
            'run': key.run,
            'team': team or [],
        }
        if add_pacing:
            data['pacing_type'] = run.pacing_type
        if add_schedule:
            data['schedule'] = {
                'start': serialize_datetime(run.start),
                'end': serialize_datetime(run.end),
            }
        return data

    def assert_data_generated_correctly(self, course_run, expected_team_data, creating=False):
        course = course_run.course
        expected = {
            'title': course_run.title_override or course.title,
            'org': course.organizations.first().key,
            'number': course.number,
            'run': StudioAPI.calculate_course_run_key_run_value(course.number, course_run.start_date_temporary),
            'schedule': {
                'start': serialize_datetime(course_run.start_date_temporary),
                'end': serialize_datetime(course_run.end_date_temporary),
            },
            'team': expected_team_data,
            'pacing_type': course_run.pacing_type_temporary,
        }
        self.assertEqual(StudioAPI.generate_data_for_studio_api(course_run, creating=creating), expected)

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

    @ddt.data(
        *product(range(1, 5), ['1T2017']),
        *product(range(5, 9), ['2T2017']),
        *product(range(9, 13), ['3T2017']),
    )
    @ddt.unpack
    def test_calculate_course_run_key_run_value(self, month, expected):
        start = datetime.datetime(2017, month, 1)
        self.assertEqual(StudioAPI.calculate_course_run_key_run_value('NONE', start=start), expected)

    def test_generate_data_for_studio_api(self):
        run = CourseRunFactory()
        editor = CourseEditorFactory(course=run.course)
        team = [
            {
                'user': editor.user.username,
                'role': 'instructor',
            },
        ]
        self.assertEqual(StudioAPI.generate_data_for_studio_api(run, True), self.make_studio_data(run, team=team))

    def test_generate_data_for_studio_api_without_team(self):
        run = CourseRunFactory()
        with mock.patch('course_discovery.apps.api.utils.logger.warning') as mock_logger:
            self.assertEqual(StudioAPI.generate_data_for_studio_api(run, True), self.make_studio_data(run))
        mock_logger.assert_called_with(
            'No course team admin specified for course [%s]. This may result in a Studio course run '
            'being created without a course team.',
            run.key.split('/')[1]
        )

    def test_calculate_course_run_key_run_value_with_multiple_runs_per_trimester(self):
        start = datetime.datetime(2017, 2, 1)

        CourseRunFactory(key='course-v1:TestX+Testing101x+1T2017')
        self.assertEqual(StudioAPI.calculate_course_run_key_run_value('TestX', start), '1T2017a')

        CourseRunFactory(key='course-v1:TestX+Testing101x+1T2017a')
        self.assertEqual(StudioAPI.calculate_course_run_key_run_value('TestX', start), '1T2017b')

    def test_update_course_run_image_in_studio_without_course_image(self):
        run = CourseRunFactory(course__image=None)
        with mock.patch('course_discovery.apps.api.utils.logger') as mock_logger:
            self.api.update_course_run_image_in_studio(run)
            mock_logger.warning.assert_called_with(
                'Card image for course run [%d] cannot be updated. The related course [%d] has no image defined.',
                run.id,
                run.course.id
            )
