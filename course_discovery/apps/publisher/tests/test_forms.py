from datetime import datetime, timedelta

import ddt
import pytest
from django.core.exceptions import ValidationError
from django.test import TestCase
from guardian.shortcuts import assign_perm
from pytz import timezone
from waffle.testutils import override_switch

from course_discovery.apps.core.models import User
from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.course_metadata.tests.factories import OrganizationFactory
from course_discovery.apps.publisher.choices import CourseRunStateChoices, PublisherUserRole
from course_discovery.apps.publisher.constants import (
    ADMIN_GROUP_NAME, INTERNAL_USER_GROUP_NAME, PUBLISHER_ENABLE_READ_ONLY_FIELDS
)
from course_discovery.apps.publisher.forms import (
    CourseEntitlementForm, CourseForm, CourseRunForm, CourseRunStateAdminForm, CourseSearchForm, CourseStateAdminForm,
    PublisherUserCreationForm, SeatForm
)
from course_discovery.apps.publisher.models import Group, OrganizationExtension, Seat
from course_discovery.apps.publisher.tests.factories import (
    CourseFactory, CourseRunFactory, CourseUserRoleFactory, OrganizationExtensionFactory, SeatFactory
)


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


@ddt.ddt
class CourseRunStateAdminFormTests(TestCase):
    """
    Tests for the publisher 'CourseRunStateAdminForm'.
    """

    @ddt.data(
        CourseRunStateChoices.Draft,
        CourseRunStateChoices.Review,
    )
    def test_clean_with_validation_error(self, course_run_state):
        """
        Verify that 'clean' raises 'ValidationError' for invalid course run state
        """
        run_state_form = CourseRunStateAdminForm()
        run_state_form.cleaned_data = {'name': course_run_state, 'owner_role': PublisherUserRole.Publisher}
        with self.assertRaises(ValidationError):
            run_state_form.clean()

    def test_clean_without_validation_error(self):
        """
        Verify that 'clean' does not raise 'ValidationError' for valid course run state
        """
        run_state_form = CourseRunStateAdminForm()
        run_state_form.cleaned_data = {
            'name': CourseRunStateChoices.Approved,
            'owner_role': PublisherUserRole.Publisher
        }
        self.assertEqual(run_state_form.clean(), run_state_form.cleaned_data)


class CourseStateAdminFormTests(TestCase):
    """
    Tests for the publisher "CourseStateAdminForm".
    """

    def test_clean_with_invalid_owner_role(self):
        """
        Test that 'clean' raises 'ValidationError' if the user role that has been assigned owner does not exist
        """
        course_state_form = CourseStateAdminForm()
        course_state_form.cleaned_data = {
            'owner_role': PublisherUserRole.CourseTeam
        }
        with self.assertRaises(ValidationError):
            course_state_form.clean()

    def test_clean_with_valid_owner_role(self):
        """
        Test that 'clean' does not raise 'ValidationError' if the user role that has been assigned owner does exist
        """
        course = CourseFactory()
        user = UserFactory()
        CourseUserRoleFactory(course=course, user=user, role=PublisherUserRole.CourseTeam)
        course_state_form = CourseStateAdminForm()
        course_state_form.cleaned_data = {
            'owner_role': PublisherUserRole.CourseTeam,
            'course': course
        }
        self.assertEqual(course_state_form.clean(), course_state_form.cleaned_data)


@ddt.ddt
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

    @ddt.data(True, False)
    def test_date_fields_are_hidden_when_switch_enabled(self, is_switch_enabled):
        with override_switch(PUBLISHER_ENABLE_READ_ONLY_FIELDS, active=is_switch_enabled):
            run_form = CourseRunForm(
                hide_start_date_field=is_switch_enabled,
                hide_end_date_field=is_switch_enabled
            )
            self.assertEqual(run_form.fields['start'].widget.is_hidden, is_switch_enabled)
            self.assertEqual(run_form.fields['end'].widget.is_hidden, is_switch_enabled)


@ddt.ddt
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

    def test_duplicate_course_number(self):
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

    @ddt.data(
        [" ", ",", "@", "(", "!", "#", "$", "%", "^", "&", "*", "+", "=", "{", "[", "ó"]
    )
    def test_invalid_course_number(self, invalid_char_list):
        """
        Verify that clean_number raises 'ValidationError' if the course number consists of special characters
        or spaces other than underscore,hyphen or period
        """
        course_form = CourseForm()
        for invalid_char in invalid_char_list:
            course_form.cleaned_data = {'number': 'course_num{}'.format(invalid_char)}
            with self.assertRaises(ValidationError):
                course_form.clean_number()

    @ddt.data(
        ["123a", "123_a", "123.a", "123-a", "XYZ123"]
    )
    def test_valid_course_number(self, valid_number_list):
        """
        Verify that clean_number allows alphanumeric(a-zA-Z0-9) characters, period, underscore and hyphen
        in course number
        """
        course_form = CourseForm()
        for valid_number in valid_number_list:
            course_form.cleaned_data = {'number': valid_number}
            self.assertEqual(course_form.clean_number(), valid_number)

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


@ddt.ddt
class PublisherCourseEntitlementFormTests(TestCase):
    without_price_error = 'Price is required.'
    negative_price_error = 'Price must be greater than or equal to 0.01'

    @ddt.data(
        (CourseEntitlementForm.VERIFIED_MODE, None, without_price_error),
        (CourseEntitlementForm.PROFESSIONAL_MODE, None, without_price_error),
        (CourseEntitlementForm.VERIFIED_MODE, -0.05, negative_price_error),
        (CourseEntitlementForm.PROFESSIONAL_MODE, -0.05, negative_price_error),
    )
    @ddt.unpack
    def test_invalid_price(self, mode, price, error_message):
        """
        Verify that form raises an error if the price is None or in -ive format
        """
        form_data = {'mode': mode, 'price': price}
        entitlement_form = CourseEntitlementForm(data=form_data)
        self.assertFalse(entitlement_form.is_valid())
        self.assertEqual(entitlement_form.errors, {'price': [error_message]})

    @ddt.data(
        (None, None),
        (None, 0),
        (CourseEntitlementForm.AUDIT_MODE, None),
        (CourseEntitlementForm.AUDIT_MODE, 0),
        (CourseEntitlementForm.VERIFIED_MODE, 50),
        (CourseEntitlementForm.PROFESSIONAL_MODE, 50),
        (CourseEntitlementForm.CREDIT_MODE, None),
        (CourseEntitlementForm.CREDIT_MODE, 0),
    )
    @ddt.unpack
    def test_valid_data(self, mode, price):
        """
        Verify that is_valid returns True for valid mode/price combos
        """
        entitlement_form = CourseEntitlementForm({'mode': mode, 'price': price})
        self.assertTrue(entitlement_form.is_valid())

    @ddt.data(
        (CourseEntitlementForm.AUDIT_MODE, 0, None),
        (CourseEntitlementForm.VERIFIED_MODE, 50, CourseEntitlementForm.VERIFIED_MODE),
        (CourseEntitlementForm.PROFESSIONAL_MODE, 50, CourseEntitlementForm.PROFESSIONAL_MODE),
        (CourseEntitlementForm.CREDIT_MODE, 0, None),
    )
    @ddt.unpack
    def test_clean_mode(self, raw_mode, raw_price, cleaned_mode):
        """
        Verify that mode is cleaned properly and that NOOP_MODES are set to None.
        """
        entitlement_form = CourseEntitlementForm({'mode': raw_mode, 'price': raw_price})
        self.assertTrue(entitlement_form.is_valid())
        self.assertEqual(entitlement_form.cleaned_data['mode'], cleaned_mode)

    def test_include_blank_mode(self):
        """
        Verify that when the include_blank_mode option is passed to the constructor, the mode field includes
        a blank option.
        """
        entitlement_form = CourseEntitlementForm(include_blank_mode=True)
        self.assertEqual([('', '')] + CourseEntitlementForm.MODE_CHOICES, entitlement_form.fields['mode'].choices)


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


@ddt.ddt
class CourseSearchFormTests(TestCase):
    """
    Tests for publisher 'CourseSearchForm'
    """

    def setUp(self):
        super().setUp()
        self.organization = OrganizationFactory()
        self.organization_extension = OrganizationExtensionFactory()
        self.user = UserFactory()
        self.user.groups.add(self.organization_extension.group)
        self.course = CourseFactory(title='Test course')
        assign_perm(
            OrganizationExtension.VIEW_COURSE, self.organization_extension.group, self.organization_extension
        )

    def test_no_user(self):
        course_form = CourseSearchForm()
        course_form.full_clean()
        self.assertFalse(course_form.is_valid())
        self.assertEqual(0, course_form.fields['course'].queryset.count())

    def _check_form(self):
        course_form = CourseSearchForm(user=self.user, data={'course': self.course.id})
        course_form.full_clean()
        return course_form.is_valid()

    def test_unrelated_course(self):
        """ Verify course search doesn't allow courses unrelated to the user. """
        self.assertFalse(self._check_form())

    def test_with_course_team(self):
        """ Verify course search allows courses in the user's organizations. """
        self.course.organizations.add(self.organization_extension.organization)  # pylint: disable=no-member
        self.assertTrue(self._check_form())

    def test_with_admin_user(self):
        """ Verify course search lets an admin access courses they aren't associated with. """
        self.user.groups.add(Group.objects.get(name=ADMIN_GROUP_NAME))
        self.assertTrue(self._check_form())

    def test_with_internal_user(self):
        """ Verify course search only lets an internal user access courses with a role for them. """
        self.user.groups.add(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))

        # Confirm that internal users aren't granted blanket access
        self.assertFalse(self._check_form())

        # But it *will* work if we add a role for this user
        CourseUserRoleFactory(course=self.course, user=self.user, role=PublisherUserRole.MarketingReviewer)
        self.assertTrue(self._check_form())


@ddt.ddt
class SeatFormTests(TestCase):
    """
    Tests for Seat Form
    """
    def test_negative_price(self):
        """
        Verify that form raises an error when price is in -ive format
        """
        form_data = {'type': Seat.VERIFIED, 'price': -0.05}
        seat_form = SeatForm(data=form_data)
        self.assertFalse(seat_form.is_valid())
        self.assertEqual(seat_form.errors, {'price': ['Price must be greater than or equal to 0.01']})

    def test_type_is_required(self):
        """
        Verify that form raises an error when type is not given
        """
        seat_form = SeatForm(data={})
        self.assertFalse(seat_form.is_valid())
        self.assertEqual(seat_form.errors, {'type': ['This field is required.']})

        seat_form_with_type = SeatForm(data={'type': Seat.AUDIT})
        self.assertTrue(seat_form_with_type.is_valid())

        seat_form_masters = SeatForm(data={'masters_track': True})
        self.assertFalse(seat_form_masters.is_valid())

    @ddt.data(
        {'type': 'audit'},
        {'type': 'audit', 'masters_track': True},
        {'type': 'audit', 'masters_track': False},
    )
    def test_create_seat_masters_track(self, form_data):
        course_run = CourseRunFactory()
        form = SeatForm(data=form_data)
        seat = form.save(course_run=course_run)
        expected_masters = 'masters_track' in form_data and form_data['masters_track']
        self.assertEqual(expected_masters, seat.masters_track)
