import json

import ddt
import jwt
import mock
import responses
from django.core.management import CommandError, call_command
from django.test import TransactionTestCase

from course_discovery.apps.core.tests.factories import PartnerFactory
from course_discovery.apps.core.tests.utils import mock_api_callback
from course_discovery.apps.course_metadata.data_loaders.api import (
    CoursesApiDataLoader, EcommerceApiDataLoader, OrganizationsApiDataLoader, ProgramsApiDataLoader
)
from course_discovery.apps.course_metadata.data_loaders.marketing_site import (
    CourseMarketingSiteDataLoader, PersonMarketingSiteDataLoader, SchoolMarketingSiteDataLoader,
    SponsorMarketingSiteDataLoader, SubjectMarketingSiteDataLoader
)
from course_discovery.apps.course_metadata.data_loaders.tests import mock_data
from course_discovery.apps.course_metadata.management.commands.refresh_course_metadata import execute_parallel_loader
from course_discovery.apps.course_metadata.tests import toggle_switch
from course_discovery.apps.course_metadata.tests.factories import CourseFactory

JSON = 'application/json'
ACCESS_TOKEN = str(jwt.encode({'preferred_username': 'bob'}, 'secret'), 'utf-8')


@ddt.ddt
class RefreshCourseMetadataCommandTests(TransactionTestCase):
    def setUp(self):
        super(RefreshCourseMetadataCommandTests, self).setUp()
        self.partner = PartnerFactory()
        partner = self.partner
        self.pipeline = [
            (SubjectMarketingSiteDataLoader, partner.marketing_site_url_root, None),
            (SchoolMarketingSiteDataLoader, partner.marketing_site_url_root, None),
            (SponsorMarketingSiteDataLoader, partner.marketing_site_url_root, None),
            (PersonMarketingSiteDataLoader, partner.marketing_site_url_root, None),
            (CourseMarketingSiteDataLoader, partner.marketing_site_url_root, None),
            (OrganizationsApiDataLoader, partner.organizations_api_url, None),
            (CoursesApiDataLoader, partner.courses_api_url, None),
            (EcommerceApiDataLoader, partner.ecommerce_api_url, 1),
            (ProgramsApiDataLoader, partner.programs_api_url, None),
        ]
        self.kwargs = {'username': 'bob'}
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

    @mock.patch('course_discovery.apps.api.cache.set_api_timestamp')
    @mock.patch('course_discovery.apps.course_metadata.management.commands.refresh_course_metadata.set_api_timestamp')
    def test_refresh_course_metadata_serial(self, mock_set_api_timestamp, mock_receiver):
        with responses.RequestsMock() as rsps:
            self.mock_access_token_api(rsps)
            self.mock_apis()

            with mock.patch('course_discovery.apps.course_metadata.management.commands.'
                            'refresh_course_metadata.execute_loader') as mock_executor:
                call_command('refresh_course_metadata')

                # Set up expected calls
                expected_calls = [mock.call(loader_class, self.partner, api_url,
                                            ACCESS_TOKEN, 'JWT', max_workers or 7, False, **self.kwargs)
                                  for loader_class, api_url, max_workers in self.pipeline]
                mock_executor.assert_has_calls(expected_calls)

        # Verify that the API cache is invalidated once, and that it isn't
        # being done by the signal receiver.
        assert mock_set_api_timestamp.call_count == 1
        assert not mock_receiver.called

    @mock.patch('course_discovery.apps.api.cache.set_api_timestamp')
    @mock.patch('course_discovery.apps.course_metadata.management.commands.refresh_course_metadata.set_api_timestamp')
    def test_refresh_course_metadata_parallel(self, mock_set_api_timestamp, mock_receiver):
        for name in ['threaded_metadata_write', 'parallel_refresh_pipeline']:
            toggle_switch(name)

        with responses.RequestsMock() as rsps:
            self.mock_access_token_api(rsps)
            self.mock_apis()

            # Courses must exist for the command to use multiple threads. If there are no
            # courses, the command won't risk race conditions between threads trying to
            # create the same course.
            CourseFactory(partner=self.partner)
            with mock.patch('concurrent.futures.ProcessPoolExecutor.submit') as mock_executor:
                call_command('refresh_course_metadata')

                # Set up expected calls
                expected_calls = [mock.call(execute_parallel_loader, loader_class,
                                            self.partner, api_url, ACCESS_TOKEN,
                                            'JWT', max_workers or 7, True, **self.kwargs)
                                  for loader_class, api_url, max_workers in self.pipeline]
                mock_executor.assert_has_calls(expected_calls, any_order=True)

        # Verify that the API cache is invalidated once, and that it isn't
        # being done by the signal receiver.
        assert mock_set_api_timestamp.call_count == 1
        assert not mock_receiver.called

    def test_refresh_course_metadata_with_invalid_partner_code(self):
        """ Verify an error is raised if an invalid partner code is passed on the command line. """
        with self.assertRaises(CommandError):
            command_args = ['--partner_code=invalid']
            call_command('refresh_course_metadata', *command_args)

    def test_refresh_course_metadata_errors_with_no_token(self):
        """ Verify an exception is raised and an error is logged if an access token is not acquired. """
        with mock.patch('edx_rest_api_client.client.EdxRestApiClient.get_oauth_access_token', side_effect=Exception):
            logger = 'course_discovery.apps.course_metadata.management.commands.refresh_course_metadata.logger'
            with mock.patch(logger) as mock_logger:
                with self.assertRaises(Exception):
                    call_command('refresh_course_metadata')
            expected_calls = [mock.call('No access token acquired through client_credential flow.')]
            mock_logger.exception.assert_has_calls(expected_calls)

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
                )
                expected_calls = [mock.call('%s failed!', loader_class.__name__) for loader_class in loader_classes]
                mock_logger.exception.assert_has_calls(expected_calls)
