# pylint: disable=no-member
import ddt
from django.core.urlresolvers import reverse
from django.test import TestCase
from django.core import mail
from django_fsm import TransitionNotAllowed

from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.course_metadata.tests import toggle_switch
from course_discovery.apps.publisher.models import State, Course
from course_discovery.apps.publisher.tests import factories
from course_discovery.apps.publisher.tests.factories import UserAttributeFactory


@ddt.ddt
class CourseRunTests(TestCase):
    """ Tests for the publisher `CourseRun` model. """

    @classmethod
    def setUpClass(cls):
        super(CourseRunTests, cls).setUpClass()
        cls.course_run = factories.CourseRunFactory(lms_course_id='test/course/id')
        cls.group = factories.GroupFactory()
        cls.user = UserFactory(is_staff=True, email='test@test-edx.org')
        cls.user.groups.add(cls.group)
        cls.course_run.course.assign_user_groups(cls.user)
        UserAttributeFactory(user=cls.user, enable_notification=True)
        toggle_switch('enable_emails', True)

    def test_str(self):
        """ Verify casting an instance to a string returns a string containing the course title and start date. """
        self.assertEqual(
            str(self.course_run),
            '{title}: {date}'.format(
                title=self.course_run.course.title, date=self.course_run.start
            )
        )

    def test_post_back_url(self):
        self.assertEqual(
            self.course_run.post_back_url,
            reverse('publisher:publisher_course_runs_edit', kwargs={'pk': self.course_run.id})
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
        self.course_run.change_state(target=target_state, user=self.user)
        self.assertEqual(self.course_run.state.name, target_state)
        self.assertEqual(self.user.email, mail.outbox[0].to[0])
        self.assert_comment(self.course_run.lms_course_id, target_state)

    def test_workflow_change_state_not_allowed(self):
        """ Verify that we can't change the workflow state from `DRAFT` to `PUBLISHED` directly. """
        self.assertEqual(self.course_run.state.name, State.DRAFT)
        with self.assertRaises(TransitionNotAllowed):
            self.course_run.change_state(target=State.PUBLISHED, user=self.user)
        self.assertEqual(len(mail.outbox), 0)

    def assert_comment(self, course, state):
        options = dict(State.CHOICES)
        msg = 'Course {course} state has been changed to {state}.'.format(
            course=course, state=str(options.get(state))
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(str(mail.outbox[0].subject), 'Course run state has changed.')
        self.assertEqual(mail.outbox[0].body.strip(), msg)

    @ddt.unpack
    @ddt.data(
        (State.DRAFT, State.NEEDS_REVIEW),
        (State.NEEDS_REVIEW, State.NEEDS_FINAL_APPROVAL),
        (State.NEEDS_FINAL_APPROVAL, State.FINALIZED),
        (State.FINALIZED, State.PUBLISHED),
        (State.PUBLISHED, State.DRAFT),
    )
    def test_workflow_change_state_without_emails(self, source_state, target_state):
        """ Verify that if emails switch is disabled then changing workflow states according
        to allowed transition but no email will be send. """
        toggle_switch('enable_emails', False)
        self.assertEqual(self.course_run.state.name, source_state)
        self.course_run.change_state(target=target_state, user=self.user)
        self.assertEqual(self.course_run.state.name, target_state)
        self.assertEqual(len(mail.outbox), 0)


class CourseTests(TestCase):
    """ Tests for the publisher `Course` model. """

    def setUp(self):
        super(CourseTests, self).setUp()
        self.course = factories.CourseFactory()
        self.course2 = factories.CourseFactory()

    def test_str(self):
        """ Verify casting an instance to a string returns a string containing the course title. """
        self.assertEqual(str(self.course), self.course.title)

    def test_post_back_url(self):
        self.assertEqual(
            self.course.post_back_url,
            reverse('publisher:publisher_courses_edit', kwargs={'pk': self.course.id})
        )

    def test_assign_user_groups(self):
        user1 = UserFactory()
        user2 = UserFactory()
        group_a = factories.GroupFactory(name="Test Group A")
        group_b = factories.GroupFactory(name="Test Group B")
        user1.groups.add(group_a)
        user2.groups.add(group_b)

        self.assertFalse(user1.has_perm(Course.VIEW_PERMISSION, self.course))
        self.assertFalse(user2.has_perm(Course.VIEW_PERMISSION, self.course2))

        self.course.assign_user_groups(user1)
        self.course2.assign_user_groups(user2)

        self.assertTrue(user1.has_perm(Course.VIEW_PERMISSION, self.course))
        self.assertTrue(user2.has_perm(Course.VIEW_PERMISSION, self.course2))

        self.assertFalse(user1.has_perm(Course.VIEW_PERMISSION, self.course2))
        self.assertFalse(user2.has_perm(Course.VIEW_PERMISSION, self.course))


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

    def test_post_back_url(self):
        self.assertEqual(
            self.seat.post_back_url,
            reverse('publisher:publisher_seats_edit', kwargs={'pk': self.seat.id})
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
