import datetime
from unittest import mock

import ddt
import pytz
from django.core.management import CommandError
from django.test import TestCase

from course_discovery.apps.course_metadata.choices import CourseRunStatus
from course_discovery.apps.course_metadata.management.commands.publish_live_course_runs import Command
from course_discovery.apps.course_metadata.tests.factories import CourseRunFactory


@ddt.ddt
@mock.patch('course_discovery.apps.course_metadata.models.CourseRun.publish')
class PublishLiveCourseRunsTests(TestCase):
    def setUp(self):
        super().setUp()
        self.now = datetime.datetime.now(pytz.UTC)
        self.past = self.now - datetime.timedelta(days=1)

    def handle(self):
        Command().handle()

    @ddt.data(
        (CourseRunStatus.Reviewed, -1, True),
        (CourseRunStatus.Reviewed, None, False),
        (CourseRunStatus.Reviewed, +1, False),
        (CourseRunStatus.Published, -1, False),
        (CourseRunStatus.Unpublished, -1, False),
    )
    @ddt.unpack
    def test_publish_conditions(self, status, delta, published, mock_publish):
        time = delta and (self.now + datetime.timedelta(days=delta))
        CourseRunFactory(status=status, go_live_date=time)

        self.handle()

        self.assertEqual(mock_publish.call_count, 1 if published else 0)

    def test_ignores_drafts(self, mock_publish):
        # Draft run doesn't get published
        run = CourseRunFactory(draft=True, status=CourseRunStatus.Reviewed, go_live_date=self.past)
        self.handle()
        self.assertEqual(mock_publish.call_count, 0)

        # But sanity check by confirming that if it *is* an official version, it does.
        run.draft = False
        run.save()
        self.handle()
        self.assertEqual(mock_publish.call_count, 1)

    def test_exception_does_not_stop_publishing(self, mock_publish):
        CourseRunFactory(status=CourseRunStatus.Reviewed, go_live_date=self.past)
        CourseRunFactory(status=CourseRunStatus.Reviewed, go_live_date=self.past)

        mock_publish.side_effect = [Exception, None]
        with self.assertRaises(CommandError):
            self.handle()

        self.assertEqual(mock_publish.call_count, 2)
