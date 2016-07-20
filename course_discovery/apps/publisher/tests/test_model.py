# pylint: disable=no-member
from django.test import TestCase

from course_discovery.apps.publisher.tests import factories


class CourseRunTests(TestCase):
    """ Tests for the publisher `CourseRun` model. """

    def setUp(self):
        super(CourseRunTests, self).setUp()
        self.course_run = factories.CourseRunFactory()

    def test_str(self):
        """ Verify casting an instance to a string returns a string containing the course title and start date. """
        self.assertEqual(
            str(self.course_run),
            '{title}: {date}'.format(
                title=self.course_run.course.title, date=self.course_run.start
            )
        )


class CourseTests(TestCase):
    """ Tests for the publisher `Course` model. """

    def setUp(self):
        super(CourseTests, self).setUp()
        self.course = factories.CourseFactory()

    def test_str(self):
        """ Verify casting an instance to a string returns a string containing the course title. """
        self.assertEqual(str(self.course), self.course.title)


class SeatTests(TestCase):
    """ Tests for the publisher `Seat` model. """

    def setUp(self):
        super(SeatTests, self).setUp()
        self.seat = factories.SeatFactory()

    def test_str(self):
        """ Verify casting an instance to a string returns a string containing the course title and seat type. """
        self.assertEqual(
            str(self.seat),
            '{course}: {type}'.format(
                course=self.seat.course_run.course.title, type=self.seat.type
            )
        )
