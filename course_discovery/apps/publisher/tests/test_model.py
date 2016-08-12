# pylint: disable=no-member
import ddt
from django.test import TestCase
from django_fsm import TransitionNotAllowed

from course_discovery.apps.publisher.models import State
from course_discovery.apps.publisher.tests import factories


@ddt.ddt
class CourseRunTests(TestCase):
    """ Tests for the publisher `CourseRun` model. """

    @classmethod
    def setUpClass(cls):
        super(CourseRunTests, cls).setUpClass()
        cls.course_run = factories.CourseRunFactory()

    def test_str(self):
        """ Verify casting an instance to a string returns a string containing the course title and start date. """
        self.assertEqual(
            str(self.course_run),
            '{title}: {date}'.format(
                title=self.course_run.course.title, date=self.course_run.start
            )
        )

    @ddt.unpack
    @ddt.data(
        (State.DRAFT, State.NEEDS_REVIEW),
        (State.NEEDS_REVIEW, State.NEEDS_FINAL_APPROVAL),
        (State.NEEDS_FINAL_APPROVAL, State.FINALIZED),
        (State.FINALIZED, State.PUBLISHED),
        (State.PUBLISHED, State.DRAFT),
    )
    def test_workflow_change_state(self, source_state, target_state):
        """ Verify that we can change the workflow states according to allowed transition. """
        self.assertEqual(self.course_run.state.name, source_state)
        self.course_run.change_state(target=target_state)
        self.assertEqual(self.course_run.state.name, target_state)

    def test_workflow_change_state_not_allowed(self):
        """ Verify that we can't change the workflow state from `DRAFT` to `PUBLISHED` directly. """
        self.assertEqual(self.course_run.state.name, State.DRAFT)
        with self.assertRaises(TransitionNotAllowed):
            self.course_run.change_state(target=State.PUBLISHED)


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


class StateTests(TestCase):
    """ Tests for the publisher `State` model. """

    def setUp(self):
        super(StateTests, self).setUp()
        self.state = factories.StateFactory()

    def test_str(self):
        """ Verify casting an instance to a string returns a string containing the current state display name. """
        self.assertEqual(
            str(self.state),
            self.state.get_name_display()
        )
