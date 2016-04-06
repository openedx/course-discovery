import datetime

import pytz
from django.test import TestCase

from course_discovery.apps.course_metadata.models import Course
from course_discovery.apps.course_metadata.tests.factories import CourseRunFactory


class CourseQuerySetTests(TestCase):
    def test_active(self):
        """ Verify the method filters the Courses to those with active course runs. """
        # Create an active course
        enrollment_end = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=30)
        active_course = CourseRunFactory(enrollment_end=enrollment_end).course

        # Create an inactive course
        enrollment_end = datetime.datetime.now(pytz.UTC) - datetime.timedelta(days=30)
        CourseRunFactory(enrollment_end=enrollment_end, course__title='ABC Test Course 2')

        self.assertListEqual(list(Course.objects.active()), [active_course])
