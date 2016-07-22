import json

import responses
from django.core.management import call_command, CommandError
from django.test import TestCase

from course_discovery.apps.core.tests.factories import PartnerFactory
from course_discovery.apps.core.tests.utils import mock_api_callback
from course_discovery.apps.course_metadata.models import Course, CourseRun, Organization, Partner, Program
from course_discovery.apps.course_metadata.tests import mock_data

ACCESS_TOKEN = 'secret'
ACCESS_TOKEN_TYPE = 'Bearer'
JSON = 'application/json'
LOGGER_NAME = 'course_metadata.management.commands.refresh_course_metadata'


class RefreshCourseMetadataCommandTests(TestCase):

    def setUp(self):
        super(RefreshCourseMetadataCommandTests, self).setUp()
        self.partner = PartnerFactory()

    def mock_access_token_api(self):
        body = {
            'access_token': ACCESS_TOKEN,
            'expires_in': 30
        }

        url = self.partner.social_auth_edx_oidc_url_root.strip('/') + '/access_token'
        responses.add_callback(
            responses.POST,
            url,
            callback=mock_api_callback(url, body, results_key=False),
            content_type=JSON
        )

        return body

    def mock_organizations_api(self):
        bodies = mock_data.ORGANIZATIONS_API_BODIES
        url = self.partner.organizations_api_url + 'organizations/'
        responses.add_callback(
            responses.GET,
            url,
            callback=mock_api_callback(url, bodies),
            content_type=JSON
        )
        return bodies

    def mock_lms_courses_api(self):
        bodies = mock_data.COURSES_API_BODIES
        url = self.partner.courses_api_url + 'courses/'
        responses.add_callback(
            responses.GET,
            url,
            callback=mock_api_callback(url, bodies, pagination=True),
            content_type=JSON
        )
        return bodies

    def mock_ecommerce_courses_api(self):

        bodies = mock_data.ECOMMERCE_API_BODIES
        url = self.partner.ecommerce_api_url + 'courses/'
        responses.add_callback(
            responses.GET,
            url,
            callback=mock_api_callback(url, bodies),
            content_type=JSON
        )
        return bodies

    def mock_marketing_courses_api(self):
        """Mock out the Marketing API. Returns a list of mocked-out course runs."""
        body = mock_data.MARKETING_API_BODY
        responses.add(
            responses.GET,
            self.partner.marketing_api_url + 'courses/',
            body=json.dumps(body),
            status=200,
            content_type='application/json'
        )
        return body['items']

    def mock_programs_api(self):
        bodies = mock_data.PROGRAMS_API_BODIES
        url = self.partner.programs_api_url + 'programs/'
        responses.add_callback(
            responses.GET,
            url,
            callback=mock_api_callback(url, bodies),
            content_type=JSON
        )
        return bodies

    @responses.activate
    def test_refresh_course_metadata(self):
        """ Verify """
        self.mock_access_token_api()
        self.mock_organizations_api()
        self.mock_lms_courses_api()
        self.mock_ecommerce_courses_api()
        self.mock_marketing_courses_api()
        self.mock_programs_api()

        call_command('refresh_course_metadata')

        partners = Partner.objects.all()
        self.assertEqual(len(partners), 1)

        organizations = Organization.objects.all()
        self.assertEqual(len(organizations), 3)

        for organization in organizations:
            self.assertEqual(organization.partner.short_code, self.partner.short_code)

        courses = Course.objects.all()
        self.assertEqual(len(courses), 2)
        for course in courses:
            self.assertEqual(course.partner.short_code, self.partner.short_code)

        course_runs = CourseRun.objects.all()
        self.assertEqual(len(course_runs), 3)
        for course_run in course_runs:
            self.assertEqual(course_run.course.partner.short_code, self.partner.short_code)

        programs = Program.objects.all()
        self.assertEqual(len(programs), 2)
        for program in programs:
            self.assertEqual(program.partner.short_code, self.partner.short_code)

        # Refresh only a specific partner
        command_args = ['--partner_code={0}'.format(partners[0].short_code)]
        call_command('refresh_course_metadata', *command_args)

        # Invalid partner code
        with self.assertRaises(CommandError):
            command_args = ['--partner_code=invalid']
            call_command('refresh_course_metadata', *command_args)

        # Access token but no token type
        with self.assertRaises(CommandError):
            command_args = ['--access_token=test-access-token']
            call_command('refresh_course_metadata', *command_args)
