import datetime

import ddt
import pytz
from django.test import TestCase

from course_discovery.apps.course_metadata.choices import CourseRunStatus
from course_discovery.apps.course_metadata.choices import ProgramStatus
from course_discovery.apps.course_metadata.models import Course, CourseRun, Program
from course_discovery.apps.course_metadata.tests.factories import CourseRunFactory, ProgramFactory


class CourseQuerySetTests(TestCase):
    def test_active(self):
        """ Verify the method filters the Courses to those with active course runs. """
        now = datetime.datetime.now(pytz.UTC)
        active_course_end = now + datetime.timedelta(days=60)
        inactive_course_end = now - datetime.timedelta(days=15)
        open_enrollment_end = now + datetime.timedelta(days=30)
        closed_enrollment_end = now - datetime.timedelta(days=30)

        # Create an active enrollable course
        active_course = CourseRunFactory(enrollment_end=open_enrollment_end, end=active_course_end).course

        # Create an active unenrollable course
        CourseRunFactory(enrollment_end=closed_enrollment_end, end=active_course_end, course__title='ABC Test Course 2')

        # Create an inactive unenrollable course
        CourseRunFactory(enrollment_end=closed_enrollment_end, end=inactive_course_end)

        # Create an active course with unrestricted enrollment
        course_without_enrollment_end = CourseRunFactory(enrollment_end=None, end=active_course_end).course

        # Create an inactive course with unrestricted enrollment
        CourseRunFactory(enrollment_end=None, end=inactive_course_end)

        # Create course with end date is NULL
        course_without_end = CourseRunFactory(enrollment_end=open_enrollment_end, end=None).course

        self.assertEqual(
            set(Course.objects.active()),
            {active_course, course_without_enrollment_end, course_without_end}
        )


@ddt.ddt
class CourseRunQuerySetTests(TestCase):
    def test_active(self):
        """ Verify the method returns only course runs currently open for enrollment or opening in the future. """
        # Create course with end date in future and enrollment_end in past.
        end = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=2)
        enrollment_end = datetime.datetime.now(pytz.UTC) - datetime.timedelta(days=1)
        CourseRunFactory(end=end, enrollment_end=enrollment_end)

        # Create course with end date in past and no enrollment_end.
        end = datetime.datetime.now(pytz.UTC) - datetime.timedelta(days=2)
        CourseRunFactory(end=end, enrollment_end=None)

        self.assertEqual(CourseRun.objects.active().count(), 0)

        # Create course with end date in future and enrollment_end in future.
        end = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=2)
        enrollment_end = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=1)
        active_enrollment_end = CourseRunFactory(end=end, enrollment_end=enrollment_end)

        # Create course with end date in future and no enrollment_end.
        active_no_enrollment_end = CourseRunFactory(end=end, enrollment_end=None)

        self.assertEqual(set(CourseRun.objects.active()), {active_enrollment_end, active_no_enrollment_end})

    def test_marketable(self):
        """ Verify the method filters CourseRuns to those with slugs. """
        course_run = CourseRunFactory()
        self.assertEqual(list(CourseRun.objects.marketable()), [course_run])

    @ddt.data(None, '')
    def test_marketable_exclusions(self, slug):
        """ Verify the method excludes CourseRuns without a slug. """
        CourseRunFactory(slug=slug)
        self.assertEqual(CourseRun.objects.marketable().count(), 0)

    @ddt.data(
        (CourseRunStatus.Unpublished, 0),
        (CourseRunStatus.Published, 1)
    )
    @ddt.unpack
    def test_marketable_unpublished_exclusions(self, status, count):
        """ Verify the method excludes CourseRuns with Unpublished status. """
        CourseRunFactory(status=status)

        self.assertEqual(CourseRun.objects.marketable().count(), count)


@ddt.ddt
class ProgramQuerySetTests(TestCase):
    @ddt.data(
        (ProgramStatus.Unpublished, False),
        (ProgramStatus.Active, True),
    )
    @ddt.unpack
    def test_marketable(self, status, is_marketable):
        """ Verify the method filters Programs to those which are active and have marketing slugs. """
        program = ProgramFactory(status=status)
        expected = [program] if is_marketable else []
        self.assertEqual(list(Program.objects.marketable()), expected)

    def test_marketable_exclusions(self):
        """ Verify the method excludes Programs without a marketing slug. """
        ProgramFactory(marketing_slug='')
        self.assertEqual(Program.objects.marketable().count(), 0)
