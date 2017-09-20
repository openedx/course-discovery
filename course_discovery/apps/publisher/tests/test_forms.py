from datetime import datetime, timedelta

import pytz
from django.core.exceptions import ValidationError
from django.test import TestCase

from course_discovery.apps.core.models import User
from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.course_metadata.models import Person
from course_discovery.apps.course_metadata.tests.factories import OrganizationFactory, PersonFactory
from course_discovery.apps.publisher.forms import CourseForm, CourseRunForm, PublisherUserCreationForm
from course_discovery.apps.publisher.tests.factories import CourseFactory, OrganizationExtensionFactory


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


class PersonModelMultipleChoiceTests(TestCase):

    def test_person_multiple_choice(self):
        """
        Verify that PersonModelMultipleChoice returns `full_name` and `profile_image_url` as choice label.
        """
        course_form = CourseRunForm()
        course_form.fields['staff'].empty_label = None

        person = PersonFactory()
        course_form.fields['staff'].queryset = Person.objects.all()

        # we need to loop through choices because it is a ModelChoiceIterator
        for __, choice_label in course_form.fields['staff'].choices:
            expected = '<img src="{url}"/><span>{full_name}</span>'.format(
                full_name=person.full_name,
                url=person.get_profile_image_url
            )
            self.assertEqual(choice_label.strip(), expected)


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
    def assert_field_valid(self, data, field_name):
        form = CourseRunForm(data=data)
        form.is_valid()
        assert field_name not in form.errors

    def test_minimum_effort(self):
        form = CourseRunForm(data={'min_effort': 1, 'max_effort': 1})
        assert not form.is_valid()
        assert form.errors['min_effort'] == ['Minimum effort must be less than maximum effort.']

        form = CourseRunForm(data={'min_effort': 2, 'max_effort': 1})
        assert not form.is_valid()
        assert form.errors['min_effort'] == ['Minimum effort must be less than maximum effort.']

        self.assert_field_valid({'min_effort': 1, 'max_effort': 2}, 'min_effort')

    def test_start(self):
        now = datetime.utcnow()
        form = CourseRunForm(data={'start': now, 'end': now - timedelta(days=1)})
        assert not form.is_valid()
        assert form.errors['start'] == ['The start date must occur before the end date.']

        form = CourseRunForm(data={'start': now, 'end': now})
        assert not form.is_valid()
        assert form.errors['start'] == ['The start date must occur before the end date.']

        self.assert_field_valid({'start': now, 'end': now + timedelta(days=1)}, 'start')

    def test_xseries_name(self):
        form = CourseRunForm(data={'is_xseries': True, 'xseries_name': ''})
        assert not form.is_valid()
        assert form.errors['xseries_name'] == ['Please provide the name of the associated XSeries.']

        self.assert_field_valid({'is_xseries': True, 'xseries_name': 'abc'}, 'xseries_name')

    def test_micromasters_name(self):
        form = CourseRunForm(data={'is_micromasters': True, 'micromasters_name': ''})
        assert not form.is_valid()
        assert form.errors['micromasters_name'] == ['Please provide the name of the associated MicroMasters.']

        self.assert_field_valid({'is_micromasters': True, 'micromasters_name': 'abc'}, 'micromasters_name')

    def test_professional_certificate_name(self):
        form = CourseRunForm(data={'is_professional_certificate': True, 'professional_certificate_name': ''})
        assert not form.is_valid()
        assert form.errors['professional_certificate_name'] == [
            'Please provide the name of the associated Professional Certificate program.']

        self.assert_field_valid({'is_professional_certificate': True, 'professional_certificate_name': 'abc'},
                                'professional_certificate_name')

    def test_enrollment_start_validation(self):
        now = datetime.utcnow().replace(tzinfo=pytz.utc)
        data = {
            'enrollment_start': now + timedelta(days=1),
            'start': now,
        }
        form = CourseRunForm(data=data)
        assert not form.is_valid()
        expected = ['The enrollment start date must occur on or before the course start date.']
        assert form.errors['enrollment_start'] == expected

        data = {
            'enrollment_start': now,
            'start': now,
        }
        self.assert_field_valid(data, 'enrollment_start')

        data = {
            'enrollment_start': now - timedelta(days=1),
            'start': now,
        }
        self.assert_field_valid(data, 'enrollment_start')

    def test_enrollment_start_default(self):
        now = datetime.utcnow().replace(tzinfo=pytz.utc)
        data = {
            'enrollment_start': None,
            'start': now,
        }
        form = CourseRunForm(data=data)
        form.is_valid()
        assert form.cleaned_data['enrollment_start'] == now

    def test_enrollment_end_validation(self):
        now = datetime.utcnow().replace(tzinfo=pytz.utc)
        data = {
            'enrollment_end': now + timedelta(days=1),
            'end': now,
        }
        form = CourseRunForm(data=data)
        assert not form.is_valid()
        expected = ['The enrollment end date must occur on or after the course end date.']
        assert form.errors['enrollment_end'] == expected

        data = {
            'enrollment_end': now,
            'end': now,
        }
        self.assert_field_valid(data, 'enrollment_end')

        data = {
            'enrollment_end': now - timedelta(days=1),
            'end': now,
        }
        self.assert_field_valid(data, 'enrollment_end')

    def test_enrollment_end_default(self):
        now = datetime.utcnow().replace(tzinfo=pytz.utc)
        data = {
            'enrollment_end': None,
            'end': now,
        }
        form = CourseRunForm(data=data)
        form.is_valid()
        assert form.cleaned_data['enrollment_end'] == now


class PublisherCustomCourseFormTests(TestCase):
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
