from django.test import TestCase

from course_discovery.apps.core.models import User
from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.course_metadata.models import Person
from course_discovery.apps.course_metadata.tests.factories import PersonFactory
from course_discovery.apps.publisher.forms import CustomCourseForm, CustomCourseRunForm


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
        Verify that UserModelChoiceField returns `username` if `full_name` empty.
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
