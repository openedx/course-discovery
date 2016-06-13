import datetime

import pytz
from django.test import TestCase

from course_catalog.apps.course_metadata.models import Course
from course_catalog.apps.course_metadata.tests.factories import CourseRunFactory


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
        course_without_end = CourseRunFactory(enrollment_end=None, end=active_course_end).course

        # Create an inactive course with unrestricted enrollment
        CourseRunFactory(enrollment_end=None, end=inactive_course_end)

        self.assertEqual(set(Course.objects.active()), {active_course, course_without_end})
