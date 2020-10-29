import json
from unittest import mock

import ddt
import responses
from django.core.management import CommandError, call_command
from django.test import TransactionTestCase
from waffle.testutils import override_switch

from course_discovery.apps.api.v1.tests.test_views.mixins import OAuth2Mixin
from course_discovery.apps.core.tests.factories import PartnerFactory
from course_discovery.apps.core.tests.utils import mock_api_callback
from course_discovery.apps.course_metadata.data_loaders.analytics_api import AnalyticsAPIDataLoader
from course_discovery.apps.course_metadata.data_loaders.api import (
    CoursesApiDataLoader, EcommerceApiDataLoader, ProgramsApiDataLoader
)
from course_discovery.apps.course_metadata.data_loaders.tests import mock_data
from course_discovery.apps.course_metadata.management.commands.refresh_course_metadata import execute_parallel_loader
from course_discovery.apps.course_metadata.models import Image, Video
from course_discovery.apps.course_metadata.tests.factories import CourseFactory

JSON = 'application/json'


@ddt.ddt
class RefreshCourseMetadataCommandTests(OAuth2Mixin, TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.partner = PartnerFactory()
        partner = self.partner
        self.pipeline = [
            (CoursesApiDataLoader, partner.courses_api_url, None),
            (EcommerceApiDataLoader, partner.ecommerce_api_url, 1),
            (ProgramsApiDataLoader, partner.programs_api_url, None),
            (AnalyticsAPIDataLoader, partner.analytics_url, 1),
        ]

        # Courses must exist for the refresh_course_metadata command to use multiple threads. If there are no
        # courses, the command won't risk race conditions between threads trying to create the same course.
        CourseFactory(partner=self.partner)

        self.mock_access_token()

    def mock_apis(self):
        self.mock_organizations_api()
        self.mock_lms_courses_api()
        self.mock_ecommerce_courses_api()
        self.mock_marketing_courses_api()
        self.mock_programs_api()

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
        self.mock_apis()

        with mock.patch('course_discovery.apps.course_metadata.management.commands.'
                        'refresh_course_metadata.execute_loader', return_value=True) as mock_executor:
            call_command('refresh_course_metadata')

            # Set up expected calls
            expected_calls = [mock.call(loader_class, self.partner, api_url, max_workers or 7, False)
                              for loader_class, api_url, max_workers in self.pipeline]
            mock_executor.assert_has_calls(expected_calls)

        # Verify that the API cache is invalidated once, and that it isn't
        # being done by the signal receiver.
        assert mock_set_api_timestamp.call_count == 1
        assert not mock_receiver.called

    @mock.patch('course_discovery.apps.api.cache.set_api_timestamp')
    @mock.patch('course_discovery.apps.course_metadata.management.commands.refresh_course_metadata.set_api_timestamp')
    @override_switch('threaded_metadata_write', True)
    @override_switch('parallel_refresh_pipeline', True)
    def test_refresh_course_metadata_parallel(self, mock_set_api_timestamp, mock_receiver):
        self.mock_apis()

        with mock.patch('concurrent.futures.ProcessPoolExecutor.submit') as mock_executor:
            call_command('refresh_course_metadata')

            # Set up expected calls
            expected_calls = [mock.call(execute_parallel_loader, loader_class,
                                        self.partner, api_url, max_workers or 7, True)
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

    def test_refresh_course_metadata_with_loader_exception(self):
        """ Verify execution continues if an individual data loader fails. """
        logger_target = 'course_discovery.apps.course_metadata.management.commands.refresh_course_metadata.logger'
        with mock.patch(logger_target) as mock_logger:
            with self.assertRaisesMessage(CommandError, 'One or more of the data loaders above failed.'):
                call_command('refresh_course_metadata')

            loader_classes = (
                CoursesApiDataLoader,
                EcommerceApiDataLoader,
                ProgramsApiDataLoader,
                AnalyticsAPIDataLoader,
            )
            expected_calls = [mock.call('%s failed!', loader_class.__name__) for loader_class in loader_classes]
            mock_logger.exception.assert_has_calls(expected_calls)

    @mock.patch('course_discovery.apps.course_metadata.management.commands.refresh_course_metadata.delete_orphans')
    def test_deletes_orphans(self, mock_delete_orphans):
        """ Verify execution culls any orphans left behind. """
        # Don't bother setting anything up - we expect to delete orphans on success or failure
        with self.assertRaisesMessage(CommandError, 'One or more of the data loaders above failed.'):
            call_command('refresh_course_metadata')

        self.assertEqual(mock_delete_orphans.call_count, 2)
        self.assertEqual({x[0][0] for x in mock_delete_orphans.call_args_list}, {Image, Video})
