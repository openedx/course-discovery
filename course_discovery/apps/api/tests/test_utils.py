import datetime
from itertools import product
from unittest import mock

import ddt
import pytest
import responses
from django.core.files.base import ContentFile
from django.test import TestCase
from opaque_keys.edx.keys import CourseKey
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from course_discovery.apps.api.utils import (
    StudioAPI, cast2int, decode_image_data, get_query_param, increment_character, increment_str
)
from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase, OAuth2Mixin
from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.core.utils import serialize_datetime
from course_discovery.apps.course_metadata.models import CourseType
from course_discovery.apps.course_metadata.tests.factories import (
    CourseEditorFactory, CourseFactory, CourseRunFactory, CourseTypeFactory
)

LOGGER_PATH = 'course_discovery.apps.api.utils.logger.exception'


def make_request(query_param=None):
    user = UserFactory()
    if query_param:
        request = APIRequestFactory().get('/', query_param)
    else:
        request = APIRequestFactory().get('/')
    request.user = user

    # Convert a Django HTTPResponse object into a rest_framework.request
    # using a generic API view. This is necessary because the drf-flex-fields
    # library relies on the `.query_params` property of the request. DRF requests
    # always have the `query_params` parameter unless the request is created using
    # `APIRequestFactory`, which yelds Django's standard `HttpRequest`.
    # Documentation: https://www.django-rest-framework.org/api-guide/testing/#forcing-authentication
    # DRF issue: https://github.com/encode/django-rest-framework/issues/6488
    return APIView().initialize_request(request)


def make_post_request(data=None):
    user = UserFactory()
    if data:
        request = APIRequestFactory().post('/', data=data)
    else:
        request = APIRequestFactory().post('/')
    request.user = user
    return APIView().initialize_request(request)


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
        assert cast2int(value, self.name) == expected

    @ddt.data('beep', '1.1')
    def test_cast_failure(self, value):
        with mock.patch(LOGGER_PATH) as mock_logger:
            with pytest.raises(ValueError):
                cast2int(value, self.name)

        assert mock_logger.called


class TestDecodeImageData(TestCase):
    def test_decode_image_data(self):
        test_image = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk' \
                     '+A8AAQUBAScY42YAAAAASUVORK5CYII='
        img_name, img_data = decode_image_data(test_image)
        assert img_name == 'tmp.png'
        assert img_data is not None
        assert isinstance(img_data, ContentFile)


class TestGetQueryParam:
    def test_with_request(self):
        factory = APIRequestFactory()
        request = Request(factory.get('/?q=1'))

        assert get_query_param(request, 'q') == 1

    def test_without_request(self):
        assert get_query_param(None, 'q') is None


@ddt.ddt
class StudioAPITests(OAuth2Mixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.mock_access_token()
        self.api = StudioAPI(self.partner)
        self.studio_url = self.partner.studio_url

    def make_studio_data(self, run, add_pacing=True, add_schedule=True, team=None, add_enrollment_dates=False):
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
        if add_enrollment_dates:
            data['schedule'] = {
                'enrollment_start': serialize_datetime(run.enrollment_start),
                'enrollment_end': serialize_datetime(run.enrollment_end),
            }
        return data

    def test_create_rerun(self):
        run1 = CourseRunFactory()
        run2 = CourseRunFactory(course=run1.course)

        expected_data = self.make_studio_data(run2)
        responses.add(responses.POST, f'{self.studio_url}api/v1/course_runs/{run1.key}/rerun/',
                      match=[responses.matchers.json_params_matcher(expected_data)])

        self.api.create_course_rerun_in_studio(run2, run1.key)

    def test_create_run(self):
        run = CourseRunFactory()

        expected_data = self.make_studio_data(run)
        responses.add(responses.POST, f'{self.studio_url}api/v1/course_runs/',
                      match=[responses.matchers.json_params_matcher(expected_data)])

        self.api.create_course_run_in_studio(run)

    def test_update_run(self):
        run = CourseRunFactory()

        expected_data = self.make_studio_data(run, add_pacing=False, add_schedule=False)
        responses.add(responses.PATCH, f'{self.studio_url}api/v1/course_runs/{run.key}/',
                      match=[responses.matchers.json_params_matcher(expected_data)])

        self.api.update_course_run_details_in_studio(run)

    @ddt.data(
        *product(range(1, 5), ['1T2017']),
        *product(range(5, 9), ['2T2017']),
        *product(range(9, 13), ['3T2017']),
    )
    @ddt.unpack
    def test_calculate_course_run_key_run_value(self, month, expected):
        start = datetime.datetime(2017, month, 1)
        assert StudioAPI.calculate_course_run_key_run_value('NONE', start=start) == expected

    def test_generate_data_for_studio_api(self):
        run = CourseRunFactory()
        editor = CourseEditorFactory(course=run.course)
        team = [
            {
                'user': editor.user.username,
                'role': 'instructor',
            },
        ]
        assert StudioAPI.generate_data_for_studio_api(run, True) == self.make_studio_data(run, team=team)

    def test_generate_data_for_studio_api_without_team(self):
        run = CourseRunFactory()
        with mock.patch('course_discovery.apps.api.utils.logger.warning') as mock_logger:
            assert StudioAPI.generate_data_for_studio_api(run, True) == self.make_studio_data(run)
        mock_logger.assert_called_with(
            'No course team admin specified for course [%s]. This may result in a Studio course run '
            'being created without a course team.',
            run.key.split('+')[1]
        )

    def test_generate_data_for_studio_api__external_course_enrollment_dates(self):
        """
        Verify that when updating the course run, the enrollment dates are added for external courses if present.
        """
        exec_ed_type = CourseTypeFactory(slug=CourseType.EXECUTIVE_EDUCATION_2U)
        run = CourseRunFactory(course=CourseFactory(type=exec_ed_type))
        with mock.patch('course_discovery.apps.api.utils.logger') as mock_logger:
            expected_data = self.make_studio_data(run, add_pacing=False, add_schedule=False, add_enrollment_dates=True)
            output_data = StudioAPI.generate_data_for_studio_api(run, False)
            assert output_data == expected_data
        mock_logger.info.assert_called_with(
            f'Enrollment information added to data {output_data} for course run {run.key}'
        )

    def test_generate_data_for_studio_api__external_course_missing_enrollment_dates(self):
        """
        Verify that when updating the course run, the enrollment dates are NOT added for external courses if missing.
        """
        exec_ed_type = CourseTypeFactory(slug=CourseType.EXECUTIVE_EDUCATION_2U)
        run = CourseRunFactory(course=CourseFactory(type=exec_ed_type), enrollment_start=None, enrollment_end=None)
        with mock.patch('course_discovery.apps.api.utils.logger') as mock_logger:
            expected_data = self.make_studio_data(run, add_pacing=False, add_schedule=False)
            output_data = StudioAPI.generate_data_for_studio_api(run, False)
            assert output_data == expected_data

        with self.assertRaises(AssertionError):
            mock_logger.info.assert_called_with(
                f'Enrollment information added to data {output_data} for course run {run.key}'
            )

    def test_calculate_course_run_key_run_value_with_multiple_runs_per_trimester(self):
        start = datetime.datetime(2017, 2, 1)

        CourseRunFactory(key='course-v1:TestX+Testing101x+1T2017')
        assert StudioAPI.calculate_course_run_key_run_value('TestX', start) == '1T2017a'

        CourseRunFactory(key='course-v1:TestX+Testing101x+1T2017a')
        assert StudioAPI.calculate_course_run_key_run_value('TestX', start) == '1T2017b'

    @ddt.data(
        (['1T2022'], '', '1T2022a'),
        (['1T2022b'], 'b', '1T2022c'),
        (['1T2022z'], 'z', '1T2022aa'),
        (['1T2022zc'], 'zc', '1T2022zd'),
        (['1T2022zz'], 'zz', '1T2022aaa'),
    )
    @ddt.unpack
    def test_get_next_run(self, existing_runs, suffix, expected):
        root = '1T2022'
        assert StudioAPI._get_next_run(root, suffix, existing_runs) == expected  # pylint: disable=W0212

    def test_update_course_run_image_in_studio_without_course_image(self):
        run = CourseRunFactory(course__image=None)
        with mock.patch('course_discovery.apps.api.utils.logger') as mock_logger:
            self.api.update_course_run_image_in_studio(run)
            mock_logger.warning.assert_called_with(
                'Card image for course run [%d] cannot be updated. The related course [%d] has no image defined.',
                run.id,
                run.course.id
            )


@ddt.ddt
class IncrementStringTests:
    @ddt.data(
        ('a', 'b'),
        ('z', 'a'),
        ('', 'a'),
    )
    @ddt.unpack
    def test_increment_character(self, value, expected):
        assert increment_character(value) == expected

    @ddt.data(
        ('a', 'b'),
        ('zz', 'aaa'),
        ('az', 'ba'),
        ('azz', 'baa'),
        ('azzaz', 'azzba'),
    )
    @ddt.unpack
    def test_increment_str(self, value, expected):
        assert increment_str(value) == expected
