from unittest import mock

from django.db.utils import IntegrityError
from django.test import TestCase

from course_discovery.apps.core.tests.factories import PartnerFactory
from course_discovery.apps.course_metadata.exceptions import MarketingSiteAPIClientException
from course_discovery.apps.course_metadata.management.commands.publish_uuids_to_drupal import Command
from course_discovery.apps.course_metadata.models import DrupalPublishUuidConfig
from course_discovery.apps.course_metadata.people import MarketingSitePeople
from course_discovery.apps.course_metadata.tests.factories import (
    CourseRunFactory, DrupalPublishUuidConfigFactory, PersonFactory
)


class TestPublishUuidsToDrupal(TestCase):
    def setUp(self):
        super().setUp()
        self.partner = PartnerFactory()
        self.course_run = CourseRunFactory(course__partner=self.partner)

    def test_handle_with_ids(self):
        DrupalPublishUuidConfigFactory(
            course_run_ids=','.join([self.course_run.key])
        )
        command = Command()
        with mock.patch('course_discovery.apps.course_metadata.publishers.'
                        'CourseRunMarketingSitePublisher.publish_obj') as mock_publish_obj:
            command.handle()
            expected_calls = [
                mock.call(self.course_run, include_uuid=True)
            ]
            mock_publish_obj.assert_has_calls(expected_calls)

    def test_handle_with_no_config(self):
        configs = DrupalPublishUuidConfig.objects.all()
        self.assertEqual(configs.count(), 0)
        command = Command()
        command_failed = False
        try:
            command.handle()
        except IntegrityError:
            command_failed = True
        assert command_failed

    def test_handle_with_no_matched_course_runs(self):
        DrupalPublishUuidConfigFactory(
            course_run_ids='NotARealCourseId'
        )
        command = Command()
        with mock.patch('course_discovery.apps.course_metadata.publishers.'
                        'CourseRunMarketingSitePublisher.publish_obj') as mock_publish_obj:
            command.handle()
            mock_publish_obj.assert_not_called()

    def test_handle_with_push_people(self):
        DrupalPublishUuidConfigFactory(
            course_run_ids='',
            push_people=True,
        )
        person = PersonFactory()
        command = Command()

        with mock.patch.object(MarketingSitePeople, 'update_or_publish_person') as cm:
            command.handle()
        self.assertEqual(cm.call_count, 1)
        self.assertEqual(cm.call_args[0][0], person)

    def test_handle_with_push_people_error(self):
        DrupalPublishUuidConfigFactory(
            course_run_ids='',
            push_people=True,
        )
        PersonFactory()
        command = Command()

        # First test that a normal exception bubbles up like we expect
        with self.assertRaises(Exception):
            with mock.patch.object(MarketingSitePeople, 'update_or_publish_person', side_effect=Exception):
                command.handle()

        # Now tests that marketing exceptions don't stop us
        with mock.patch.object(
            MarketingSitePeople, 'update_or_publish_person', side_effect=MarketingSiteAPIClientException
        ) as cm:
            command.handle()
            self.assertEqual(cm.call_count, 1)
