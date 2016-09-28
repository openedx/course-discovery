# pylint: disable=no-member
from unittest import mock

from django.test import TestCase

import ddt

from course_discovery.apps.course_metadata.tests.factories import OrganizationFactory
from course_discovery.apps.publisher.models import Seat, State
from course_discovery.apps.publisher.tests import factories
from course_discovery.apps.publisher.wrappers import CourseRunWrapper


@ddt.ddt
class CourseRunWrapperTests(TestCase):
    """ Tests for the publisher `BaseWrapper` model. """

    def setUp(self):
        super(CourseRunWrapperTests, self).setUp()
        self.course_run = factories.CourseRunFactory()
        self.course = self.course_run.course
        organization_1 = OrganizationFactory()
        organization_2 = OrganizationFactory()

        self.course.organizations.add(organization_1)
        self.course.organizations.add(organization_2)
        self.course.save()

        self.wrapped_course_run = CourseRunWrapper(self.course_run)

    def test_title(self):
        """ Verify that the wrapper can override course_run title. """
        self.assertEqual(self.wrapped_course_run.title, self.course_run.course.title)

    def test_partner(self):
        """ Verify that the wrapper can return partner values. """
        partner = "/".join([org.key for org in self.course_run.course.organizations.all()])
        self.assertEqual(self.wrapped_course_run.partner, partner)

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
        """ Verify that the wrapper return the course type according to the
        available seats.
        """
        self._generate_seats(seats_list)
        wrapper_object = CourseRunWrapper(self.course_run)
        self.assertEqual(wrapper_object.course_type, course_type)

    def test_organization_key(self):
        """ Verify that the wrapper return the organization key. """
        course = factories.CourseFactory()
        course_run = factories.CourseRunFactory(course=course)
        wrapped_course_run = CourseRunWrapper(course_run)
        self.assertEqual(wrapped_course_run.organization_key, None)

        organization = OrganizationFactory()
        course.organizations.add(organization)
        wrapped_course_run = CourseRunWrapper(course_run)
        self.assertEqual(wrapped_course_run.organization_key, organization.key)

    def test_verified_seat_price(self):
        """ Verify that the wrapper return the verified seat price. """
        self.assertEqual(self.wrapped_course_run.verified_seat_price, None)

        seat = factories.SeatFactory(type=Seat.VERIFIED, course_run=self.course_run)
        wrapped_course_run = CourseRunWrapper(self.course_run)
        self.assertEqual(wrapped_course_run.verified_seat_price, seat.price)

    def test_credit_seat(self):
        """ Verify that the wrapper return the credit seat. """
        self.assertEqual(self.wrapped_course_run.credit_seat, None)
        seat = factories.SeatFactory(
            type=Seat.CREDIT, course_run=self.course_run, credit_provider='ASU', credit_hours=9
        )

        wrapped_course_run = CourseRunWrapper(self.course_run)
        self.assertEqual(wrapped_course_run.credit_seat, seat)

    def test_workflow_state(self):
        """ Verify that the wrapper can return workflow state. """
        self.assertEqual(self.wrapped_course_run.workflow_state, State.DRAFT.title())
