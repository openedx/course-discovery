import datetime

import mock
import pytz
from django.core.management import CommandError
from django.test import TestCase

from course_discovery.apps.course_metadata.choices import CourseRunStatus
from course_discovery.apps.course_metadata.exceptions import UnpublishError
from course_discovery.apps.course_metadata.management.commands.unpublish_inactive_runs import Command
from course_discovery.apps.course_metadata.tests.factories import CourseFactory, CourseRunFactory


@mock.patch('course_discovery.apps.course_metadata.models.Course.unpublish_inactive_runs')
class PublishLiveCourseRunsTests(TestCase):
    def handle(self):
        Command().handle()

    def test_filtering_and_grouping(self, mock_unpublish):
        course1 = CourseFactory()
        course2 = CourseFactory()
        course3 = CourseFactory()
        run1 = CourseRunFactory(status=CourseRunStatus.Published, course=course2)  # all intentionally out of order
        _run2 = CourseRunFactory(status=CourseRunStatus.Unpublished, course=course2)
        _run3 = CourseRunFactory(status=CourseRunStatus.Unpublished, course=course3)
        run4 = CourseRunFactory(status=CourseRunStatus.Published, course=course1)
        run5 = CourseRunFactory(status=CourseRunStatus.Published, course=course2)

        self.handle()

        self.assertNumQueries(3)
        self.assertEqual(mock_unpublish.call_count, 2)
        self.assertEqual(mock_unpublish.call_args_list[0], mock.call(published_runs={run4}))
        self.assertEqual(mock_unpublish.call_args_list[1], mock.call(published_runs={run1, run5}))

    def test_republish(self, _mock_unpublish):
        time1 = datetime.datetime.now(pytz.UTC) - datetime.timedelta(days=10)
        time2 = datetime.datetime.now(pytz.UTC) - datetime.timedelta(days=9)

        # Add a course with an old published run (just to test we leave it alone)
        course1 = CourseFactory()
        run1 = CourseRunFactory(status=CourseRunStatus.Published, course=course1, start=time1, announcement=time1)
        run2 = CourseRunFactory(status=CourseRunStatus.Unpublished, course=course1, start=time2, announcement=time1)

        # Add a course with no active runs (to test that we do republish it)
        course2 = CourseFactory()
        run3 = CourseRunFactory(status=CourseRunStatus.Unpublished, course=course2, start=time1, announcement=time1)
        run4 = CourseRunFactory(status=CourseRunStatus.Unpublished, course=course2, start=time2, announcement=time1)

        self.handle()

        for run in [run1, run2, run3, run4]:
            run.refresh_from_db()

        self.assertEqual(run1.status, CourseRunStatus.Published)
        self.assertEqual(run2.status, CourseRunStatus.Unpublished)
        self.assertEqual(run3.status, CourseRunStatus.Unpublished)
        self.assertEqual(run4.status, CourseRunStatus.Published)  # only one that changed

    def test_exception_does_not_stop_command(self, mock_unpublish):
        CourseRunFactory(status=CourseRunStatus.Published)
        CourseRunFactory(status=CourseRunStatus.Published)

        mock_unpublish.side_effect = [UnpublishError, None]
        with self.assertRaises(CommandError):
            self.handle()

        self.assertEqual(mock_unpublish.call_count, 2)
