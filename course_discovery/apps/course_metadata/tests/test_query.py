import datetime

import ddt
import pytz
from django.test import TestCase

from course_discovery.apps.course_metadata.choices import CourseRunStatus, ProgramStatus
from course_discovery.apps.course_metadata.models import Course, CourseRun, Program
from course_discovery.apps.course_metadata.tests.factories import CourseRunFactory, ProgramFactory, SeatFactory


class CourseQuerySetTests(TestCase):
    def test_active(self):
        """
        Verify the method filters Courses to those with active CourseRuns.
        """
        now = datetime.datetime.now(pytz.UTC)
        active_course_end = now + datetime.timedelta(days=60)
        inactive_course_end = now - datetime.timedelta(days=15)
        open_enrollment_end = now + datetime.timedelta(days=30)
        closed_enrollment_end = now - datetime.timedelta(days=30)

        # Create an active, enrollable course run
        active_course = CourseRunFactory(enrollment_end=open_enrollment_end, end=active_course_end).course

        # Create an active, unenrollable course run
        CourseRunFactory(enrollment_end=closed_enrollment_end, end=active_course_end, course__title='ABC Test Course 2')

        # Create an inactive, unenrollable course run
        CourseRunFactory(enrollment_end=closed_enrollment_end, end=inactive_course_end)

        # Create an active course run with an unspecified enrollment end
        course_without_enrollment_end = CourseRunFactory(enrollment_end=None, end=active_course_end).course

        # Create an inactive course run with an unspecified enrollment end
        CourseRunFactory(enrollment_end=None, end=inactive_course_end)

        # Create an enrollable course run with an unspecified end date
        course_without_end = CourseRunFactory(enrollment_end=open_enrollment_end, end=None).course

        assert set(Course.objects.active()) == {
            active_course, course_without_enrollment_end, course_without_end
        }

    def test_marketable(self):
        """
        Verify the method filters Courses to those with marketable CourseRuns.
        """
        # Courses whose runs have null or empty slugs are excluded, even if
        # those runs are published and have seats.
        for invalid_slug in (None, ''):
            excluded_course_run = CourseRunFactory(slug=invalid_slug)
            SeatFactory(course_run=excluded_course_run)

        # Courses whose runs have no seats are excluded, even if those runs
        # are published and have valid slugs.
        CourseRunFactory()

        # Courses whose runs are unpublished are excluded, even if those runs
        # have seats and valid slugs.
        excluded_course_run = CourseRunFactory(status=CourseRunStatus.Unpublished)
        SeatFactory(course_run=excluded_course_run)

        # Courses with at least one run that is published and has seats and a valid
        # slug are included.
        included_course_run = CourseRunFactory()
        SeatFactory(course_run=included_course_run)

        included_course = included_course_run.course
        # This run has no seats and will be excluded, but we still expect its parent
        # course to be included.
        CourseRunFactory(course=included_course)

        assert set(Course.objects.marketable()) == {included_course}


@ddt.ddt
class CourseRunQuerySetTests(TestCase):
    def test_active(self):
        """ Verify the method returns only course runs currently open for enrollment or opening in the future. """
        now = datetime.datetime.now(pytz.UTC)
        active_course_end = now + datetime.timedelta(days=60)
        inactive_course_end = now - datetime.timedelta(days=15)
        open_enrollment_end = now + datetime.timedelta(days=30)
        closed_enrollment_end = now - datetime.timedelta(days=30)

        # Create course with end date in future and enrollment_end in past.
        CourseRunFactory(end=active_course_end, enrollment_end=closed_enrollment_end)

        # Create course with end date in past and no enrollment_end.
        CourseRunFactory(end=inactive_course_end, enrollment_end=None)

        self.assertEqual(CourseRun.objects.active().count(), 0)

        # Create course with end date in future and enrollment_end in future.
        active_enrollment_end = CourseRunFactory(end=active_course_end, enrollment_end=open_enrollment_end)

        # Create course with end date in future and no enrollment_end.
        active_no_enrollment_end = CourseRunFactory(end=active_course_end, enrollment_end=None)

        # Create course with no end date and enrollment date in future.
        active_no_end_date = CourseRunFactory(end=None, enrollment_end=open_enrollment_end)

        self.assertEqual(
            set(CourseRun.objects.active()),
            {active_enrollment_end, active_no_enrollment_end, active_no_end_date}
        )

    def test_enrollable(self):
        """ Verify the method returns only course runs currently open for enrollment. """
        past = datetime.datetime.now(pytz.UTC) - datetime.timedelta(days=2)
        future = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=2)

        enrollable = CourseRunFactory(enrollment_start=past, enrollment_end=future)
        enrollable_no_enrollment_end = CourseRunFactory(enrollment_start=past, enrollment_end=None)
        enrollable_no_enrollment_start = CourseRunFactory(enrollment_start=None, enrollment_end=future)
        CourseRunFactory(enrollment_start=future)
        CourseRunFactory(enrollment_end=past)

        # order doesn't matter
        assert list(CourseRun.objects.enrollable().order_by('id')) == sorted([
            enrollable, enrollable_no_enrollment_end, enrollable_no_enrollment_start
        ], key=lambda x: x.id)

    def test_marketable(self):
        """ Verify the method filters CourseRuns to those with slugs. """
        course_run = CourseRunFactory()
        SeatFactory(course_run=course_run)

        self.assertEqual(list(CourseRun.objects.marketable()), [course_run])

    @ddt.data(None, '')
    def test_marketable_exclusions(self, slug):
        """ Verify the method excludes CourseRuns without a slug. """
        course_run = CourseRunFactory(slug=slug)
        SeatFactory(course_run=course_run)

        self.assertEqual(CourseRun.objects.marketable().exists(), False)

    @ddt.data(True, False)
    def test_marketable_seats_exclusions(self, has_seats):
        """ Verify that the method excludes CourseRuns without seats. """
        course_run = CourseRunFactory()

        if has_seats:
            SeatFactory(course_run=course_run)

        self.assertEqual(CourseRun.objects.marketable().exists(), has_seats)

    @ddt.data(True, False)
    def test_marketable_unpublished_exclusions(self, is_published):
        """ Verify the method excludes CourseRuns with Unpublished status. """
        course_run = CourseRunFactory(status=CourseRunStatus.Unpublished)
        SeatFactory(course_run=course_run)

        if is_published:
            course_run.status = CourseRunStatus.Published
            course_run.save()

        self.assertEqual(CourseRun.objects.marketable().exists(), is_published)


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
