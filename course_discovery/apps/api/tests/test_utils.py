import ddt
import mock
import pytest
from django.test import TestCase
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from course_discovery.apps.api.utils import (
    cast2int,
    get_query_param,
    get_queryset_filtered_on_organization
)
from course_discovery.apps.course_metadata.models import Course, CourseRun

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


class TestGetQuerysetFilteredOnOrganization:

    @pytest.mark.django_db
    def test_courses_runs_filter_on_edx_shortname(self):
        edx_org_filter = 'course__authoring_organizations__key'
        edx_org_short_name = 'edx'
        edx_course_run_key = 'course-v1:edX+DemoX+Demo_Course'
        expected_course_runs_queryset = CourseRun.objects.filter(course__authoring_organizations__key=edx_org_short_name)

        course_runs_queryset = CourseRun.objects.filter(key=edx_course_run_key)
        actual_course_runs_queryset = get_queryset_filtered_on_organization(course_runs_queryset, edx_org_filter, edx_org_short_name)

        assert len(actual_course_runs_queryset) == len(expected_course_runs_queryset)

    @pytest.mark.django_db
    def test_course_filter_on_edx_shortname(self):
        edx_org_filter = 'authoring_organizations__key'
        edx_org_short_name = 'edx'
        edx_course_key = 'course-v1:edX+DemoX+Demo_Course'
        expected_courses_queryset = Course.objects.filter(authoring_organizations__key=edx_org_short_name)

        courses_queryset = Course.objects.filter(key=edx_course_key)
        actual_courses_queryset = get_queryset_filtered_on_organization(courses_queryset, edx_org_filter, edx_org_short_name)

        assert len(actual_courses_queryset) == len(expected_courses_queryset)
