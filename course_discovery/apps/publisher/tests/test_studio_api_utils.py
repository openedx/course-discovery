import datetime
from itertools import product

import mock
import pytest
from waffle.testutils import override_switch

from course_discovery.apps.core.utils import serialize_datetime
from course_discovery.apps.course_metadata.tests.factories import CourseFactory as DiscoveryCourseFactory
from course_discovery.apps.course_metadata.tests.factories import CourseRunFactory as DiscoveryCourseRunFactory
from course_discovery.apps.course_metadata.tests.factories import OrganizationFactory
from course_discovery.apps.publisher.choices import PublisherUserRole
from course_discovery.apps.publisher.constants import PUBLISHER_REMOVE_PACING_TYPE_EDITING
from course_discovery.apps.publisher.studio_api_utils import StudioAPI
from course_discovery.apps.publisher.tests.factories import CourseRunFactory, CourseUserRoleFactory

test_data = (
    list(product(range(1, 5), ['1T2017'])) +
    list(product(range(5, 8), ['2T2017'])) +
    list(product(range(9, 13), ['3T2017']))
)


@pytest.mark.django_db
@pytest.mark.parametrize('month,expected', test_data)
def test_calculate_course_run_key_run_value(month, expected):
    course_run = CourseRunFactory(start=datetime.datetime(2017, month, 1))
    assert StudioAPI.calculate_course_run_key_run_value(course_run) == expected


@pytest.mark.django_db
def test_calculate_course_run_key_run_value_with_multiple_runs_per_trimester():
    number = 'TestX'
    organization = OrganizationFactory()
    partner = organization.partner
    course_key = '{org}+{number}'.format(org=organization.key, number=number)
    discovery_course = DiscoveryCourseFactory(partner=partner, key=course_key)
    DiscoveryCourseRunFactory(key='course-v1:TestX+Testing101x+1T2017', course=discovery_course)
    course_run = CourseRunFactory(
        start=datetime.datetime(2017, 2, 1),
        lms_course_id=None,
        course__organizations=[organization],
        course__number=number
    )
    assert StudioAPI.calculate_course_run_key_run_value(course_run) == '1T2017a'

    DiscoveryCourseRunFactory(key='course-v1:TestX+Testing101x+1T2017a', course=discovery_course)
    assert StudioAPI.calculate_course_run_key_run_value(course_run) == '1T2017b'


def assert_data_generated_correctly(course_run, expected_team_data):
    course = course_run.course
    expected = {
        'title': course_run.title_override or course.title,
        'org': course.organizations.first().key,
        'number': course.number,
        'run': StudioAPI.calculate_course_run_key_run_value(course_run),
        'schedule': {
            'start': serialize_datetime(course_run.start_date_temporary),
            'end': serialize_datetime(course_run.end),
        },
        'team': expected_team_data,
        'pacing_type': course_run.pacing_type_temporary,
    }
    assert StudioAPI.generate_data_for_studio_api(course_run) == expected


@pytest.mark.django_db
@override_switch(PUBLISHER_REMOVE_PACING_TYPE_EDITING, active=True)
def test_generate_data_for_studio_api():
    course_run = CourseRunFactory(course__organizations=[OrganizationFactory()])
    course = course_run.course
    role = CourseUserRoleFactory(course=course, role=PublisherUserRole.CourseTeam)
    team = [
        {
            'user': role.user.username,
            'role': 'instructor',
        },
    ]
    assert_data_generated_correctly(course_run, team)


@pytest.mark.django_db
@override_switch(PUBLISHER_REMOVE_PACING_TYPE_EDITING, active=True)
def test_generate_data_for_studio_api_without_team():
    course_run = CourseRunFactory(course__organizations=[OrganizationFactory()])

    with mock.patch('course_discovery.apps.publisher.studio_api_utils.logger.warning') as mock_logger:
        assert_data_generated_correctly(course_run, [])
        mock_logger.assert_called_with(
            'No course team admin specified for course [%s]. This may result in a Studio course run '
            'being created without a course team.',
            course_run.course.number
        )


@pytest.mark.django_db
def test_update_course_run_image_in_studio_without_course_image():
    publisher_course_run = CourseRunFactory(course__image=None)
    api = StudioAPI(None)

    with mock.patch('course_discovery.apps.publisher.studio_api_utils.logger') as mock_logger:
        api.update_course_run_image_in_studio(publisher_course_run)
        mock_logger.warning.assert_called_with(
            'Card image for course run [%d] cannot be updated. The related course [%d] has no image defined.',
            publisher_course_run.id,
            publisher_course_run.course.id
        )
