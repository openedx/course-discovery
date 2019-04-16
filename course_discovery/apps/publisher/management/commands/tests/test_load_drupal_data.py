import datetime

from django.core.management import call_command
from django.test import TestCase

import jwt
import mock
import responses
from course_discovery.apps.core.tests.factories import PartnerFactory
from course_discovery.apps.core.tests.utils import mock_api_callback
from course_discovery.apps.course_metadata.data_loaders.tests import mock_data
from course_discovery.apps.course_metadata.models import CourseRun as CourseMetadataCourseRun
from course_discovery.apps.course_metadata.tests.factories import CourseRunFactory, OrganizationFactory
from course_discovery.apps.publisher.management.commands.load_drupal_data import DrupalCourseMarketingSiteDataLoader
from course_discovery.apps.publisher.models import CourseRun as PublisherCourseRun
from course_discovery.apps.publisher.tests.factories import CourseFactory as PublisherCourseFactory
from course_discovery.apps.publisher.tests.factories import DrupalLoaderConfigFactory

ACCESS_TOKEN = str(jwt.encode({'preferred_username': 'bob'}, 'secret'), 'utf-8')


class TestLoadDrupalData(TestCase):
    def setUp(self):
        super(TestLoadDrupalData, self).setUp()
        self.command_name = 'load_drupal_data'
        self.partner = PartnerFactory()
        self.course_run = CourseRunFactory(course__partner=self.partner)
        self.course_run.course.canonical_course_run = self.course_run
        self.course_run.course.save()

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
            content_type='application/json'
        )

        return body

    def test_load_drupal_data_with_partner(self):
        with responses.RequestsMock() as rsps:
            self.mock_access_token_api(rsps)

            with mock.patch('course_discovery.apps.publisher.management.commands.'
                            'load_drupal_data.execute_loader') as mock_executor:
                config = DrupalLoaderConfigFactory.create(
                    course_run_ids='course-v1:SC+BreadX+3T2015',
                    partner_code=self.partner.short_code,
                    load_unpublished_course_runs=False
                )
                call_command('load_drupal_data')

                expected_calls = [
                    mock.call(DrupalCourseMarketingSiteDataLoader,
                              self.partner,
                              self.partner.marketing_site_url_root,
                              ACCESS_TOKEN,
                              'JWT',
                              1,
                              False,
                              set(config.course_run_ids.split(',')),
                              config.load_unpublished_course_runs,
                              username=jwt.decode(ACCESS_TOKEN, verify=False)['preferred_username'])
                ]
                mock_executor.assert_has_calls(expected_calls)

    def test_process_node(self):
        # Set the end date in the future
        data = mock_data.UNIQUE_MARKETING_SITE_API_COURSE_BODIES[0]
        data['field_course_end_date'] = datetime.datetime.max.strftime('%s')
        OrganizationFactory.create(
            uuid=data.get('field_course_school_node', {})[0].get('uuid')
        )

        config = DrupalLoaderConfigFactory.create(
            course_run_ids=data.get('field_course_id'),
            partner_code=self.partner.short_code,
            load_unpublished_course_runs=False
        )
        data_loader = DrupalCourseMarketingSiteDataLoader(
            self.partner,
            self.partner.marketing_site_url_root,
            ACCESS_TOKEN,
            'JWT',
            1,  # Make this a constant of 1 for no concurrency
            False,
            set(config.course_run_ids.split(',')),
            config.load_unpublished_course_runs
        )

        # Need to mock this method so that the GET isn't sent out to the test data server
        with mock.patch('course_discovery.apps.publisher.dataloader.create_courses.'
                        'transfer_course_image'):
            data_loader.process_node(mock_data.UNIQUE_MARKETING_SITE_API_COURSE_BODIES[0])
            course_metadata_course_run = CourseMetadataCourseRun.objects.get(key=data.get('field_course_id'))
            self.assertIsNotNone(course_metadata_course_run)
            self.assertIsNotNone(course_metadata_course_run.course)
            publisher_course_run = PublisherCourseRun.objects.get(lms_course_id=course_metadata_course_run.key)
            self.assertIsNotNone(publisher_course_run)
            self.assertIsNotNone(publisher_course_run.course)

    def test_process_node_archived(self):
        # Set the end date in the past
        data = mock_data.UNIQUE_MARKETING_SITE_API_COURSE_BODIES[0]
        data['field_course_end_date'] = datetime.datetime.min.strftime('%s')
        OrganizationFactory.create(
            uuid=data.get('field_course_school_node', {})[0].get('uuid')
        )

        config = DrupalLoaderConfigFactory.create(
            course_run_ids=data.get('field_course_id'),
            partner_code=self.partner.short_code,
            load_unpublished_course_runs=False
        )
        data_loader = DrupalCourseMarketingSiteDataLoader(
            self.partner,
            self.partner.marketing_site_url_root,
            ACCESS_TOKEN,
            'JWT',
            1,  # Make this a constant of 1 for no concurrency
            False,
            set(config.course_run_ids.split(',')),
            config.load_unpublished_course_runs
        )

        # Need to mock this method so that the GET isn't sent out to the test data server
        with mock.patch('course_discovery.apps.publisher.dataloader.create_courses.'
                        'transfer_course_image'):
            data_loader.process_node(mock_data.UNIQUE_MARKETING_SITE_API_COURSE_BODIES[0])
            course_metadata_course_run = CourseMetadataCourseRun.objects.filter(key=data.get('field_course_id'))
            self.assertEqual(course_metadata_course_run.count(), 0)

    def test_process_node_not_whitelisted(self):
        # Set the end date in the future
        data = mock_data.UNIQUE_MARKETING_SITE_API_COURSE_BODIES[0]
        data['field_course_end_date'] = datetime.datetime.max.strftime('%s')
        OrganizationFactory.create(
            uuid=data.get('field_course_school_node', {})[0].get('uuid')
        )

        config = DrupalLoaderConfigFactory.create(
            course_run_ids='SomeFakeCourseRunId',
            partner_code=self.partner.short_code,
            load_unpublished_course_runs=False
        )
        data_loader = DrupalCourseMarketingSiteDataLoader(
            self.partner,
            self.partner.marketing_site_url_root,
            ACCESS_TOKEN,
            'JWT',
            1,  # Make this a constant of 1 for no concurrency
            False,
            set(config.course_run_ids.split(',')),
            config.load_unpublished_course_runs
        )

        # Need to mock this method so that the GET isn't sent out to the test data server
        with mock.patch('course_discovery.apps.publisher.dataloader.create_courses.'
                        'transfer_course_image'):
            for body in mock_data.UNIQUE_MARKETING_SITE_API_COURSE_BODIES:
                data_loader.process_node(body)
            # Even after looping through all course bodies no new rows should be created
            course_metadata_course_run = CourseMetadataCourseRun.objects.filter(key=data.get('field_course_id'))
            self.assertEqual(course_metadata_course_run.count(), 0)

    def test_process_node_run_created(self):
        # Set the end date in the future
        data = mock_data.UNIQUE_MARKETING_SITE_API_COURSE_BODIES[0]
        data['field_course_end_date'] = datetime.datetime.max.strftime('%s')
        data['status'] = '1'
        OrganizationFactory.create(
            uuid=data.get('field_course_school_node', {})[0].get('uuid')
        )

        self.course_run.key = data.get('field_course_id')
        self.course_run.save()

        config = DrupalLoaderConfigFactory.create(
            course_run_ids=data.get('field_course_id'),
            partner_code=self.partner.short_code,
            load_unpublished_course_runs=False
        )
        data_loader = DrupalCourseMarketingSiteDataLoader(
            self.partner,
            self.partner.marketing_site_url_root,
            ACCESS_TOKEN,
            'JWT',
            1,  # Make this a constant of 1 for no concurrency
            False,
            set(config.course_run_ids.split(',')),
            config.load_unpublished_course_runs
        )

        with mock.patch('course_discovery.apps.publisher.signals.create_course_run_in_studio_receiver') as mock_signal:
            # Need to mock this method so that the GET isn't sent out to the test data server
            with mock.patch('course_discovery.apps.publisher.dataloader.create_courses.'
                            'transfer_course_image'):
                data_loader.process_node(mock_data.UNIQUE_MARKETING_SITE_API_COURSE_BODIES[0])
                mock_signal.assert_not_called()

        course_metadata_course_run = CourseMetadataCourseRun.objects.get(key=data.get('field_course_id'))
        self.assertIsNotNone(course_metadata_course_run)
        self.assertIsNotNone(course_metadata_course_run.course)
        publisher_course_run = PublisherCourseRun.objects.get(lms_course_id=course_metadata_course_run.key)
        self.assertIsNotNone(publisher_course_run)
        self.assertIsNotNone(publisher_course_run.course)

    def test_load_unpublished_course_runs_with_flag_enabled(self):
        # Set the end date in the future
        data = mock_data.UNIQUE_MARKETING_SITE_API_COURSE_BODIES[0]
        data['field_course_end_date'] = datetime.datetime.max.strftime('%s')
        # Set the status to unpublished
        data['status'] = '0'
        OrganizationFactory.create(
            uuid=data.get('field_course_school_node', {})[0].get('uuid')
        )

        self.course_run.key = data.get('field_course_id')
        self.course_run.save()

        PublisherCourseFactory.create(course_metadata_pk=self.course_run.course.id)

        load_unpublished_course_runs = True

        config = DrupalLoaderConfigFactory.create(
            course_run_ids=data.get('field_course_id'),
            partner_code=self.partner.short_code,
            load_unpublished_course_runs=load_unpublished_course_runs
        )
        data_loader = DrupalCourseMarketingSiteDataLoader(
            self.partner,
            self.partner.marketing_site_url_root,
            ACCESS_TOKEN,
            'JWT',
            1,  # Make this a constant of 1 for no concurrency
            False,
            set(config.course_run_ids.split(',')),
            load_unpublished_course_runs
        )

        # Need to mock this method so that the GET isn't sent out to the test data server
        with mock.patch('course_discovery.apps.publisher.dataloader.create_courses.'
                        'transfer_course_image'):
            data_loader.process_node(mock_data.UNIQUE_MARKETING_SITE_API_COURSE_BODIES[0])

        course_metadata_course_run = CourseMetadataCourseRun.objects.get(key=data.get('field_course_id'))
        self.assertIsNotNone(course_metadata_course_run)
        self.assertIsNotNone(course_metadata_course_run.course)
        publisher_course_run = PublisherCourseRun.objects.get(lms_course_id=course_metadata_course_run.key)
        self.assertIsNotNone(publisher_course_run)
        self.assertIsNotNone(publisher_course_run.course)

    def test_load_unpublished_course_runs_with_flag_enabled_no_course_found(self):
        # Set the end date in the future
        data = mock_data.UNIQUE_MARKETING_SITE_API_COURSE_BODIES[0]
        data['field_course_end_date'] = datetime.datetime.max.strftime('%s')
        # Set the status to unpublished
        data['status'] = '0'
        OrganizationFactory.create(
            uuid=data.get('field_course_school_node', {})[0].get('uuid')
        )

        self.course_run.key = data.get('field_course_id')
        self.course_run.save()

        load_unpublished_course_runs = True

        config = DrupalLoaderConfigFactory.create(
            course_run_ids=data.get('field_course_id'),
            partner_code=self.partner.short_code,
            load_unpublished_course_runs=load_unpublished_course_runs
        )
        data_loader = DrupalCourseMarketingSiteDataLoader(
            self.partner,
            self.partner.marketing_site_url_root,
            ACCESS_TOKEN,
            'JWT',
            1,  # Make this a constant of 1 for no concurrency
            False,
            set(config.course_run_ids.split(',')),
            load_unpublished_course_runs
        )

        logger_target = 'course_discovery.apps.publisher.management.commands.load_drupal_data.logger'
        with mock.patch(logger_target) as mock_logger:
            # Need to mock this method so that the GET isn't sent out to the test data server
            with mock.patch('course_discovery.apps.publisher.dataloader.create_courses.'
                            'transfer_course_image'):
                data_loader.process_node(mock_data.UNIQUE_MARKETING_SITE_API_COURSE_BODIES[0])
            expected_calls = [mock.call('No Publisher Course found for Course Run [%s]', self.course_run.key)]
            mock_logger.info.assert_has_calls(expected_calls)
