import json

import ddt
import mock
import responses
from django.core.management import call_command, CommandError
from django.test import TestCase

from course_discovery.apps.core.tests.factories import PartnerFactory
from course_discovery.apps.core.tests.utils import mock_api_callback
from course_discovery.apps.course_metadata.data_loaders.api import (
    OrganizationsApiDataLoader, CoursesApiDataLoader, EcommerceApiDataLoader, ProgramsApiDataLoader,
)
from course_discovery.apps.course_metadata.data_loaders.marketing_site import (
    XSeriesMarketingSiteDataLoader, SubjectMarketingSiteDataLoader, SchoolMarketingSiteDataLoader,
    SponsorMarketingSiteDataLoader, PersonMarketingSiteDataLoader, CourseMarketingSiteDataLoader
)
from course_discovery.apps.course_metadata.data_loaders.tests import mock_data
from course_discovery.apps.course_metadata.tests import toggle_switch
from course_discovery.apps.course_metadata.tests.factories import CourseFactory

ACCESS_TOKEN = 'secret'
JSON = 'application/json'


@ddt.ddt
class RefreshCourseMetadataCommandTests(TestCase):
    def setUp(self):
        super(RefreshCourseMetadataCommandTests, self).setUp()
        self.partner = PartnerFactory()

        self.mock_access_token_api()

    def mock_apis(self):
        self.mock_organizations_api()
        self.mock_lms_courses_api()
        self.mock_ecommerce_courses_api()
        self.mock_marketing_courses_api()
        self.mock_programs_api()

    def mock_access_token_api(self, requests_mock=None):
        body = {
            'access_token': ACCESS_TOKEN,
            'expires_in': 30
        }
        requests_mock = requests_mock or responses

        url = self.partner.oidc_url_root.strip('/') + '/access_token'
        requests_mock.add_callback(
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
            self.partner.marketing_site_api_url + 'courses/',
            body=json.dumps(body),
            status=200,
            content_type=JSON
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

    @ddt.data(True, False)
    def test_refresh_course_metadata(self, is_parallel):
        if is_parallel:
            for name in ['threaded_metadata_write', 'parallel_refresh_pipeline']:
                toggle_switch(name)

        with responses.RequestsMock() as rsps:
            self.mock_access_token_api(rsps)
            self.mock_apis()

            # Courses must exist for the command to use multiple threads. If there are no
            # courses, the command won't risk race conditions between threads trying to
            # create the same course.
            CourseFactory(partner=self.partner)

            call_command('refresh_course_metadata')

    def test_refresh_course_metadata_with_invalid_partner_code(self):
        """ Verify an error is raised if an invalid partner code is passed on the command line. """
        with self.assertRaises(CommandError):
            command_args = ['--partner_code=invalid']
            call_command('refresh_course_metadata', *command_args)

    def test_refresh_course_metadata_with_no_token_type(self):
        """ Verify an error is raised if an access token is passed in without a token type. """
        with self.assertRaises(CommandError):
            command_args = ['--access_token=test-access-token']
            call_command('refresh_course_metadata', *command_args)

    def test_refresh_course_metadata_with_loader_exception(self):
        """ Verify execution continues if an individual data loader fails. """
        with responses.RequestsMock() as rsps:
            self.mock_access_token_api(rsps)

            logger_target = 'course_discovery.apps.course_metadata.management.commands.refresh_course_metadata.logger'
            with mock.patch(logger_target) as mock_logger:
                call_command('refresh_course_metadata')

                loader_classes = (
                    SubjectMarketingSiteDataLoader,
                    SchoolMarketingSiteDataLoader,
                    SponsorMarketingSiteDataLoader,
                    PersonMarketingSiteDataLoader,
                    CourseMarketingSiteDataLoader,
                    OrganizationsApiDataLoader,
                    CoursesApiDataLoader,
                    EcommerceApiDataLoader,
                    ProgramsApiDataLoader,
                    XSeriesMarketingSiteDataLoader,
                )
                expected_calls = [mock.call('%s failed!', loader_class.__name__) for loader_class in loader_classes]
                mock_logger.exception.assert_has_calls(expected_calls)
