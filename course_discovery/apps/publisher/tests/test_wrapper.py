# pylint: disable=no-member
from datetime import datetime, timedelta
from unittest import mock

import ddt
from django.test import TestCase

from course_discovery.apps.course_metadata.choices import CourseRunPacing
from course_discovery.apps.course_metadata.tests.factories import (
    OrganizationFactory, PersonFactory, PersonSocialNetworkFactory, PositionFactory
)
from course_discovery.apps.publisher.choices import CourseRunStateChoices, PublisherUserRole
from course_discovery.apps.publisher.models import Seat
from course_discovery.apps.publisher.tests import factories
from course_discovery.apps.publisher.wrappers import CourseRunWrapper


@ddt.ddt
class CourseRunWrapperTests(TestCase):
    """ Tests for the publisher `BaseWrapper` model. """

    def setUp(self):
        super(CourseRunWrapperTests, self).setUp()
        self.course_run = factories.CourseRunFactory()
        self.course = self.course_run.course

        self.wrapped_course_run = CourseRunWrapper(self.course_run)

    def test_title(self):
        """ Verify that the wrapper can override course_run title. """
        self.assertEqual(self.wrapped_course_run.title, self.course_run.course.title)

    def test_model_attr(self):
        """ Verify that the wrapper passes through object values not defined on wrapper. """
        self.assertEqual(self.wrapped_course_run.lms_course_id, self.course_run.lms_course_id)

    def test_callable(self):
        mock_callable = mock.Mock(return_value='callable_value')
        mock_obj = mock.MagicMock(callable_attr=mock_callable)
        wrapper = CourseRunWrapper(mock_obj)

        self.assertEqual(wrapper.callable_attr(), 'callable_value')

    def _generate_seats(self, modes):
        for mode in modes:
            factories.SeatFactory(type=mode, course_run=self.course_run)

    @ddt.unpack
    @ddt.data(
        ([], Seat.AUDIT),
        ([Seat.AUDIT], Seat.AUDIT),
        ([Seat.AUDIT, Seat.CREDIT, Seat.VERIFIED], Seat.CREDIT),
        ([Seat.AUDIT, Seat.VERIFIED], Seat.VERIFIED),
        ([Seat.PROFESSIONAL], Seat.PROFESSIONAL),
    )
    def test_course_type_(self, seats_list, course_type):
        """ Verify that the wrapper return the course type according to the available seats."""
        self._generate_seats(seats_list)
        wrapper_object = CourseRunWrapper(self.course_run)
        self.assertEqual(wrapper_object.course_type, course_type)

    def test_seat_price(self):
        """ Verify that the wrapper return the seat price. """
        self.assertEqual(self.wrapped_course_run.seat_price, None)

        seat = factories.SeatFactory(type=Seat.VERIFIED, course_run=self.course_run)
        wrapped_course_run = CourseRunWrapper(self.course_run)
        self.assertEqual(wrapped_course_run.seat_price, seat.price)

    def test_credit_seat_price(self):
        """ Verify that the wrapper return the credit seat price. """
        self.assertEqual(self.wrapped_course_run.credit_seat_price, None)

        seat = factories.SeatFactory(type=Seat.CREDIT, course_run=self.course_run)
        wrapped_course_run = CourseRunWrapper(self.course_run)
        self.assertEqual(wrapped_course_run.credit_seat_price, seat.credit_price)

    def test_credit_seat(self):
        """ Verify that the wrapper return the credit seat. """
        self.assertEqual(self.wrapped_course_run.credit_seat, None)
        seat = factories.SeatFactory(
            type=Seat.CREDIT, course_run=self.course_run, credit_provider='ASU', credit_hours=9
        )

        wrapped_course_run = CourseRunWrapper(self.course_run)
        self.assertEqual(wrapped_course_run.credit_seat, seat)

    def test_is_authored_in_studio(self):
        """ Verify that the wrapper return the is_authored_in_studio. """
        self.assertFalse(self.wrapped_course_run.is_authored_in_studio)
        self.course_run.lms_course_id = 'test/course/id'
        self.course_run.save()
        self.assertTrue(self.wrapped_course_run.is_authored_in_studio)

    def test_is_self_paced(self):
        """ Verify that the wrapper return the is_self_paced. """
        self.course_run.pacing_type = CourseRunPacing.Instructor
        self.course_run.save()
        self.assertFalse(self.wrapped_course_run.is_self_paced)
        self.course_run.pacing_type = CourseRunPacing.Self
        self.course_run.save()
        self.assertTrue(self.wrapped_course_run.is_self_paced)

    def test_mdc_submission_due_date(self):
        """ Verify that the wrapper return the mdc_submission_due_date. """
        current_date = datetime.today()
        expected_date = current_date - timedelta(days=10)
        self.course_run.start = current_date
        self.course_run.save()
        self.assertEqual(self.wrapped_course_run.mdc_submission_due_date, expected_date)

    @ddt.data(True, False)
    def test_is_seo_reviews(self, is_seo_review):
        """ Verify that the wrapper return the is_seo_review. """
        self.course.is_seo_review = is_seo_review
        self.course.save()

        self.assertEqual(
            self.wrapped_course_run.is_seo_review,
            self.course.is_seo_review
        )

    def test_course_team_admin(self):
        """ Verify that the wrapper return the course team admin. """
        self.assertEqual(self.wrapped_course_run.course_team_admin, self.course.course_team_admin)

    def _change_state_and_owner(self, course_run_state):
        """
        Change course run state to review and ownership to project coordinator.
        """
        course_run_state.name = CourseRunStateChoices.Review
        course_run_state.change_owner_role(PublisherUserRole.ProjectCoordinator)

    def test_course_team_status(self):
        """
        Verify that course_team_status returns right statuses.
        """
        course_run_state = factories.CourseRunStateFactory(
            course_run=self.course_run, owner_role=PublisherUserRole.CourseTeam
        )
        assert self.wrapped_course_run.course_team_status == 'Draft'

        self._change_state_and_owner(course_run_state)
        assert self.wrapped_course_run.course_team_status == 'Submitted for Project Coordinator Review'

        course_run_state.change_owner_role(PublisherUserRole.CourseTeam)
        assert self.wrapped_course_run.course_team_status == 'Awaiting Course Team Review'

    def test_owner_role_is_publisher(self):
        """
        Verify that owner_role_is_publisher returns true if owner is publisher and false otherwise
        """
        course_run_state = factories.CourseRunStateFactory(
            course_run=self.course_run, owner_role=PublisherUserRole.Publisher
        )
        self.assertEqual(self.wrapped_course_run.owner_role_is_publisher, True)

        course_run_state.change_owner_role(PublisherUserRole.CourseTeam)
        self.assertEqual(self.wrapped_course_run.owner_role_is_publisher, False)

    def test_internal_user_status(self):
        """
        Verify that internal_user_status returns right statuses.
        """
        course_run_state = factories.CourseRunStateFactory(
            course_run=self.course_run, owner_role=PublisherUserRole.CourseTeam
        )
        assert self.wrapped_course_run.internal_user_status == 'N/A'

        self._change_state_and_owner(course_run_state)
        assert self.wrapped_course_run.internal_user_status == 'Awaiting Project Coordinator Review'

        course_run_state.change_owner_role(PublisherUserRole.CourseTeam)
        assert self.wrapped_course_run.internal_user_status == 'Approved by Project Coordinator'

    def test_preview_declined(self):
        """
        Verify that preview_declined returns False for no preview_declined
        """
        self.assertEqual(self.wrapped_course_run.preview_declined, False)
