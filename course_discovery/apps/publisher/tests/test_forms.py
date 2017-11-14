from datetime import datetime, timedelta

import pytest
from django.core.exceptions import ValidationError
from django.test import TestCase
from pytz import timezone
from waffle.testutils import override_switch

from course_discovery.apps.core.models import User
from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.course_metadata.tests.factories import OrganizationFactory
from course_discovery.apps.publisher.forms import CourseForm, CourseRunForm, PublisherUserCreationForm, SeatForm
from course_discovery.apps.publisher.models import Seat
from course_discovery.apps.publisher.tests.factories import CourseFactory, OrganizationExtensionFactory, SeatFactory


class UserModelChoiceFieldTests(TestCase):
    """
    Tests for the publisher model "UserModelChoiceField".
    """

    def setUp(self):
        super(UserModelChoiceFieldTests, self).setUp()
        self.course_form = CourseForm()

    def test_course_form(self):
        """
        Verify that UserModelChoiceField returns `full_name` as choice label.
        """
        user = UserFactory(username='test_user', full_name='Test Full Name')
        self._assert_choice_label(user.full_name)

    def test_team_admin_without_full_name(self):
        """
        Verify that UserModelChoiceField returns `username` if `full_name` is empty.
        """
        user = UserFactory(username='test_user', full_name='', first_name='', last_name='')
        self._assert_choice_label(user.username)

    def _assert_choice_label(self, expected_name):
        self.course_form.fields['team_admin'].queryset = User.objects.all()
        self.course_form.fields['team_admin'].empty_label = None

        # we need to loop through choices because it is a ModelChoiceIterator
        for __, choice_label in self.course_form.fields['team_admin'].choices:
            self.assertEqual(choice_label, expected_name)


class PublisherUserCreationFormTests(TestCase):
    """
    Tests for the publisher `PublisherUserCreationForm`.
    """

    def test_clean_groups(self):
        """
        Verify that `clean` raises `ValidationError` error if no group is selected.
        """
        user_form = PublisherUserCreationForm()
        user_form.cleaned_data = {'username': 'test_user', 'groups': []}
        with self.assertRaises(ValidationError):
            user_form.clean()

        user_form.cleaned_data['groups'] = ['test_group']
        self.assertEqual(user_form.clean(), user_form.cleaned_data)


class PublisherCourseRunEditFormTests(TestCase):
    """
    Tests for the publisher 'CourseRunForm'.
    """

    def test_minimum_effort(self):
        """
        Verify that 'clean' raises 'ValidationError' error if Minimum effort is greater
        than Maximum effort.
        """
        run_form = CourseRunForm()
        run_form.cleaned_data = {'min_effort': 4, 'max_effort': 2}
        with self.assertRaises(ValidationError):
            run_form.clean()

        run_form.cleaned_data['min_effort'] = 1
        self.assertEqual(run_form.clean(), run_form.cleaned_data)

    def test_minimum_maximum_effort_equality(self):
        """
        Verify that 'clean' raises 'ValidationError' error if Minimum effort and
        Maximum effort are equal.
        """
        run_form = CourseRunForm()
        run_form.cleaned_data = {'min_effort': 4, 'max_effort': 4}
        with self.assertRaises(ValidationError) as err:
            run_form.clean()

        self.assertEqual(str(err.exception), "{'min_effort': ['Minimum effort and Maximum effort can not be same']}")
        run_form.cleaned_data['min_effort'] = 2
        self.assertEqual(run_form.clean(), run_form.cleaned_data)

    def test_minimum__effort_is_not_empty(self):
        """
        Verify that 'clean' raises 'ValidationError' error if Maximum effort is
        empty.
        """
        run_form = CourseRunForm()
        run_form.cleaned_data = {'min_effort': 4}
        with self.assertRaises(ValidationError) as err:
            run_form.clean()

        self.assertEqual(str(err.exception), "{'max_effort': ['Maximum effort can not be empty']}")
        run_form.cleaned_data['max_effort'] = 5
        self.assertEqual(run_form.clean(), run_form.cleaned_data)

    def test_course_run_dates(self):
        """
        Verify that 'clean' raises 'ValidationError' if the Start date is in the past
        Or if the Start date is after the End date
        """
        run_form = CourseRunForm()
        current_datetime = datetime.now(timezone('US/Central'))
        run_form.cleaned_data = {'start': current_datetime + timedelta(days=3),
                                 'end': current_datetime + timedelta(days=1)}
        with self.assertRaises(ValidationError):
            run_form.clean()

        run_form.cleaned_data['start'] = current_datetime + timedelta(days=1)
        run_form.cleaned_data['end'] = current_datetime + timedelta(days=3)
        self.assertEqual(run_form.clean(), run_form.cleaned_data)

    def test_course_run_xseries(self):
        """
        Verify that 'clean' raises 'ValidationError' if the is_xseries is checked
         but no xseries_name has been entered
        """
        run_form = CourseRunForm()
        run_form.cleaned_data = {'is_xseries': True, 'xseries_name': ''}
        with self.assertRaises(ValidationError):
            run_form.clean()

        run_form.cleaned_data['xseries_name'] = "Test Name"
        self.assertEqual(run_form.clean(), run_form.cleaned_data)

    def test_course_run_micromasters(self):
        """
         Verify that 'clean' raises 'ValidationError' if the is_micromasters is checked
         but no micromasters_name has been entered
        """
        run_form = CourseRunForm()
        run_form.cleaned_data = {'is_micromasters': True, 'micromasters_name': ''}
        with self.assertRaises(ValidationError):
            run_form.clean()

        run_form.cleaned_data['micromasters_name'] = "Test Name"
        self.assertEqual(run_form.clean(), run_form.cleaned_data)

    def test_course_run_professional_certificate(self):
        """
         Verify that 'clean' raises 'ValidationError' if the is_professional_certificate is checked
         but no professional_certificate_name has been entered
        """
        run_form = CourseRunForm()
        run_form.cleaned_data = {'is_professional_certificate': True, 'professional_certificate_name': ''}
        with self.assertRaises(ValidationError):
            run_form.clean()

        run_form.cleaned_data['professional_certificate_name'] = "Test Name"
        self.assertEqual(run_form.clean(), run_form.cleaned_data)


class PublisherCustomCourseFormTests(TestCase):
    """
    Tests for publisher 'CourseForm'
    """

    def setUp(self):
        super(PublisherCustomCourseFormTests, self).setUp()
        self.course_form = CourseForm()
        self.organization = OrganizationFactory()
        self.course = CourseFactory(title='Test', number='a123', organizations=[self.organization])

    def setup_course(self, **course_kwargs):
        """
        Creates the course and add organization and admin to this course.

        Returns:
            course: a course object
            course_admin: a user object
        """
        organization_extension = OrganizationExtensionFactory()
        defaults = {
            'organizations': [organization_extension.organization],
        }
        defaults.update(course_kwargs)
        course = CourseFactory(**defaults)

        course_admin = UserFactory()
        course_admin.groups.add(organization_extension.group)

        return course, course_admin

    def test_duplicate_title(self):
        """
        Verify that clean raises 'ValidationError' if the course title is a duplicate of another course title
        within the same organization
        """
        course_form = CourseForm()
        course_form.cleaned_data = {'title': 'Test', 'number': '123a', 'organization': self.organization}
        with self.assertRaises(ValidationError):
            course_form.clean()

        course_form.cleaned_data['title'] = "Test2"
        self.assertEqual(course_form.clean(), course_form.cleaned_data)

    def test_duplicate_number(self):
        """
        Verify that clean raises 'ValidationError' if the course number is a duplicate of another course number
        within the same organization
        """
        course_form = CourseForm()
        course_form.cleaned_data = {'title': 'Test2', 'number': 'a123', 'organization': self.organization}
        with self.assertRaises(ValidationError):
            course_form.clean()

        course_form.cleaned_data['number'] = "123a"
        self.assertEqual(course_form.clean(), course_form.cleaned_data)

    def test_invalid_number(self):
        """
        Verify that clean_number raises 'ValidationError' if the course number consists of special characters
        or spaces
        """
        course_form = CourseForm()
        course_form.cleaned_data = {'number': '123 a'}
        with self.assertRaises(ValidationError):
            course_form.clean_number()

        course_form.cleaned_data['number'] = "123.a"
        self.assertEqual(course_form.clean_number(), "123.a")

        course_form.cleaned_data['number'] = "123a"
        self.assertEqual(course_form.clean_number(), "123a")

    def test_course_title_formatting(self):
        """
        Verify that course_title is properly escaped and saved in database while
        updating the course
        """
        course, course_admin = self.setup_course(image=None)
        assert course.title != 'áçã'

        organization = course.organizations.first().id
        course_from_data = {
            'title': '&aacute;&ccedil;&atilde;',
            'number': course.number,
            'organization': organization,
            'team_admin': course_admin.id
        }
        course_form = CourseForm(
            **{'data': course_from_data, 'instance': course, 'user': course_admin,
               'organization': organization}
        )
        assert course_form.is_valid()
        course_form.save()
        course.refresh_from_db()
        assert course.title == 'áçã'


@pytest.mark.django_db
class TestSeatForm:
    @override_switch('publisher_create_audit_seats_for_verified_course_runs', active=True)
    @pytest.mark.parametrize('seat_type', (Seat.NO_ID_PROFESSIONAL, Seat.PROFESSIONAL,))
    def test_remove_audit_seat_for_professional_course_runs(self, seat_type):
        seat = SeatFactory(type=seat_type)
        audit_seat = SeatFactory(type=Seat.AUDIT, course_run=seat.course_run)
        form = SeatForm(instance=seat)
        form.save()
        assert list(seat.course_run.seats.all()) == [seat]
        assert not Seat.objects.filter(pk=audit_seat.pk).exists()

    @override_switch('publisher_create_audit_seats_for_verified_course_runs', active=True)
    def test_audit_only_seat_not_modified(self):
        seat = SeatFactory(type=Seat.AUDIT)
        form = SeatForm(instance=seat)
        form.save()
        assert list(seat.course_run.seats.all()) == [seat]

    @override_switch('publisher_create_audit_seats_for_verified_course_runs', active=True)
    @pytest.mark.parametrize('seat_type', (Seat.CREDIT, Seat.VERIFIED,))
    def test_create_audit_seat_for_credit_and_verified_course_runs(self, seat_type):
        seat = SeatFactory(type=seat_type)
        form = SeatForm(instance=seat)
        form.save()
        assert seat.course_run.seats.count() == 2
        assert seat.course_run.seats.filter(type=Seat.AUDIT, price=0).exists()
