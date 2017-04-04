# pylint: disable=no-member
from datetime import datetime, timedelta
from unittest import mock

import ddt
from django.test import TestCase

from course_discovery.apps.core.tests.helpers import make_image_file
from course_discovery.apps.course_metadata.choices import CourseRunPacing
from course_discovery.apps.course_metadata.tests.factories import OrganizationFactory, PersonFactory, PositionFactory
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
        organization = OrganizationFactory()

        self.course.organizations.add(organization)
        self.course.save()

        self.wrapped_course_run = CourseRunWrapper(self.course_run)

    def test_title(self):
        """ Verify that the wrapper can override course_run title. """
        self.assertEqual(self.wrapped_course_run.title, self.course_run.course.title)

    def test_partner(self):
        """ Verify that the wrapper can return partner values. """
        organization = OrganizationFactory()
        self.course.organizations.add(organization)
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
        """ Verify that the wrapper return the course type according to the available seats."""
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

    def test_organization_name(self):
        """ Verify that the wrapper return the organization name. """
        course = factories.CourseFactory()
        course_run = factories.CourseRunFactory(course=course)
        wrapped_course_run = CourseRunWrapper(course_run)
        self.assertEqual(wrapped_course_run.organization_name, None)

        organization = OrganizationFactory()
        course.organizations.add(organization)
        wrapped_course_run = CourseRunWrapper(course_run)
        self.assertEqual(wrapped_course_run.organization_name, organization.name)

    def test_is_authored_in_studio(self):
        """ Verify that the wrapper return the is_authored_in_studio. """
        self.assertFalse(self.wrapped_course_run.is_authored_in_studio)
        self.course_run.lms_course_id = 'test/course/id'
        self.course_run.save()
        self.assertTrue(self.wrapped_course_run.is_authored_in_studio)

    def test_is_multiple_partner_course(self):
        """ Verify that the wrapper return the is_multiple_partner_course. """
        self.assertFalse(self.wrapped_course_run.is_multiple_partner_course)
        organization = OrganizationFactory()
        self.course.organizations.add(organization)

        self.assertTrue(self.wrapped_course_run.is_multiple_partner_course)

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

    def test_keywords(self):
        """ Verify that the wrapper return the course keywords. """
        self.assertEqual(
            self.wrapped_course_run.keywords,
            self.course.keywords_data
        )

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

    def test_course_image(self):
        """ Verify that the wrapper return the course image. """
        self.assertIsNone(self.wrapped_course_run.course_image)

        self.course.image = make_image_file('test_banner1.jpg')
        self.course.save()

        self.assertEqual(self.wrapped_course_run.course_image, self.course.image)

    def test_course_staff(self):
        """Verify that the wrapper return staff list."""
        staff = PersonFactory()

        # another staff with position by default staff has no position associated.
        staff_2 = PersonFactory()
        position = PositionFactory(person=staff_2)

        self.course_run.staff = [staff, staff_2]
        self.course_run.save()

        expected = [
            {
                'full_name': staff.full_name,
                'image_url': staff.get_profile_image_url,
                'profile_url': staff.profile_url,
            },
            {
                'full_name': staff_2.full_name,
                'image_url': staff_2.get_profile_image_url,
                'profile_url': staff_2.profile_url,
                'position': position.title,
                'organization': position.organization_name,
            }
        ]

        self.assertEqual(self.wrapped_course_run.course_staff, expected)
