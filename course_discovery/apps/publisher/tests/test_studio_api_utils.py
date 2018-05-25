import datetime
import mock

from course_discovery.apps.course_metadata.tests.factories import CourseFactory as DiscoveryCourseFactory
from course_discovery.apps.course_metadata.tests.factories import CourseRunFactory as DiscoveryCourseRunFactory
from course_discovery.apps.course_metadata.tests.factories import OrganizationFactory
from course_discovery.apps.publisher.choices import PublisherUserRole
from course_discovery.apps.publisher.studio_api_utils import StudioAPI
from course_discovery.apps.publisher.tests.factories import CourseRunFactory, CourseUserRoleFactory
from course_discovery.apps.publisher.tests.utils import MockedStartEndDateTestCase


class StudioApiUtilTestCase(MockedStartEndDateTestCase):
    def test_calculate_course_run_key_run_value(self):
        for month in range(1, 13):
            if month < 5:
                expected = '1T2017'
            elif month < 9:
                expected = '2T2017'
            else:
                expected = '3T2017'
            self.start_date_mock.return_value = datetime.datetime(2017, month, 1)
            course_run = CourseRunFactory()
            assert StudioAPI.calculate_course_run_key_run_value(
                course_run,
                self.start_date_mock.return_value
            ) == expected

    def test_calculate_course_run_key_run_value_with_multiple_runs_per_trimester(self):
        number = 'TestX'
        organization = OrganizationFactory()
        partner = organization.partner
        course_key = '{org}+{number}'.format(org=organization.key, number=number)
        discovery_course = DiscoveryCourseFactory(partner=partner, key=course_key)
        DiscoveryCourseRunFactory(key='course-v1:TestX+Testing101x+1T2017', course=discovery_course)
        self.start_date_mock.return_value = datetime.datetime(2017, 2, 1)
        course_run = CourseRunFactory(
            lms_course_id=None,
            course__organizations=[organization],
            course__number=number
        )
        assert StudioAPI.calculate_course_run_key_run_value(course_run, self.start_date_mock.return_value) == '1T2017a'

        DiscoveryCourseRunFactory(key='course-v1:TestX+Testing101x+1T2017a', course=discovery_course)
        assert StudioAPI.calculate_course_run_key_run_value(course_run, self.start_date_mock.return_value) == '1T2017b'

    def assert_data_generated_correctly(self, course_run, expected_team_data):
        course = course_run.course
        expected = {
            'title': course_run.title_override or course.title,
            'org': course.organizations.first().key,
            'number': course.number,
            'run': StudioAPI.calculate_course_run_key_run_value(course_run, self.start_date_mock.return_value),
            'team': expected_team_data,
            'pacing_type': course_run.pacing_type,
        }
        assert StudioAPI.generate_data_for_studio_api(course_run) == expected

    def test_generate_data_for_studio_api(self):
        course_run = CourseRunFactory(course__organizations=[OrganizationFactory()])
        course = course_run.course
        role = CourseUserRoleFactory(course=course, role=PublisherUserRole.CourseTeam)
        team = [
            {
                'user': role.user.username,
                'role': 'instructor',
            },
        ]
        self.assert_data_generated_correctly(course_run, team)

    def test_generate_data_for_studio_api_without_team(self):
        course_run = CourseRunFactory(course__organizations=[OrganizationFactory()])

        with mock.patch('course_discovery.apps.publisher.studio_api_utils.logger.warning') as mock_logger:
            self.assert_data_generated_correctly(course_run, [])
            mock_logger.assert_called_with(
                'No course team admin specified for course [%s]. This may result in a Studio course run '
                'being created without a course team.',
                course_run.course.number
            )

    def test_update_course_run_image_in_studio_without_course_image(self):
        publisher_course_run = CourseRunFactory(course__image=None)
        api = StudioAPI(None)

        with mock.patch('course_discovery.apps.publisher.studio_api_utils.logger') as mock_logger:
            api.update_course_run_image_in_studio(publisher_course_run)
            mock_logger.warning.assert_called_with(
                'Card image for course run [%d] cannot be updated. The related course [%d] has no image defined.',
                publisher_course_run.id,
                publisher_course_run.course.id
            )
