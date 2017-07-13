from datetime import datetime, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from pytz import timezone

from course_discovery.apps.core.models import User
from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.course_metadata.models import Person
from course_discovery.apps.course_metadata.tests.factories import OrganizationFactory, PersonFactory
from course_discovery.apps.publisher.forms import CustomCourseForm, CustomCourseRunForm, PublisherUserCreationForm
from course_discovery.apps.publisher.tests.factories import CourseFactory, OrganizationExtensionFactory


class UserModelChoiceFieldTests(TestCase):
    """
    Tests for the publisher model "UserModelChoiceField".
    """

    def setUp(self):
        super(UserModelChoiceFieldTests, self).setUp()
        self.course_form = CustomCourseForm()

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
        course_form = CustomCourseRunForm()
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
    """
    Tests for the publisher 'CustomCourseRunForm'.
    """

    def test_minimum_effort(self):
        """
        Verify that 'clean' raises 'ValidationError' error if Minimum effort is greater
        than Maximum effort.
        """
        run_form = CustomCourseRunForm()
        run_form.cleaned_data = {'min_effort': 4, 'max_effort': 2}
        with self.assertRaises(ValidationError):
            run_form.clean()

        run_form.cleaned_data['min_effort'] = 1
        self.assertEqual(run_form.clean(), run_form.cleaned_data)

    def test_course_run_dates(self):
        """
        Verify that 'clean' raises 'ValidationError' if the Start date is in the past
        Or if the Start date is after the End date
        """
        run_form = CustomCourseRunForm()
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
        run_form = CustomCourseRunForm()
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
        run_form = CustomCourseRunForm()
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
        run_form = CustomCourseRunForm()
        run_form.cleaned_data = {'is_professional_certificate': True, 'professional_certificate_name': ''}
        with self.assertRaises(ValidationError):
            run_form.clean()

        run_form.cleaned_data['professional_certificate_name'] = "Test Name"
        self.assertEqual(run_form.clean(), run_form.cleaned_data)


class PublisherCustomCourseFormTests(TestCase):
    """
    Tests for publisher 'CustomCourseForm'
    """
    def setUp(self):
        super(PublisherCustomCourseFormTests, self).setUp()
        self.course_form = CustomCourseForm()
        self.course = CourseFactory(title="Test", number="a123")
        self.organization = OrganizationFactory()
        self.course.organizations.add(self.organization)

    def setup_course(self, **course_kwargs):
        """
        Creates the course and add organization and admin to this course.

        Returns:
            course: a course object
            course_admin: a user object
        """
        course = CourseFactory(**course_kwargs)
        course_admin = UserFactory(username='course_admin')
        organization_extension = OrganizationExtensionFactory()
        organization = organization_extension.organization

        course_admin.groups.add(organization_extension.group)
        course.organizations.add(organization)
        return course, course_admin

    def test_duplicate_title(self):
        """
        Verify that clean raises 'ValidationError' if the course title is a duplicate of another course title
        within the same organization
        """
        course_form = CustomCourseForm()
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
        course_form = CustomCourseForm()
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
        course, course_admin = self.setup_course(title='test_course')
        organization = course.organizations.all()[0].id
        course_from_data = {
            'title': '&aacute;&ccedil;&atilde;',
            'number': course.number,
            'organization': organization,
            'team_admin': course_admin.id
        }
        course_form = CustomCourseForm(
            **{'data': course_from_data, 'instance': course, 'user': course_admin,
               'organization': organization}
        )
        self.assertTrue(course_form.is_valid())
        course_updated_data = course_form.save()
        self.assertTrue(course_updated_data.title, 'áçã')
