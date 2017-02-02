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

    def test_course_form(self):
        """
        Verify that UserModelChoiceField returns `full_name` as choice label.
        """
        course_form = CustomCourseForm()
        user = UserFactory(username='test_user', full_name='Test Full Name')
        course_form.fields['team_admin'].queryset = User.objects.all()
        course_form.fields['team_admin'].empty_label = None

        # we need to loop through choices because it is a ModelChoiceIterator
        for __, choice_label in course_form.fields['team_admin'].choices:
            self.assertEqual(choice_label, user.full_name)


class PersonModelMultipleChoiceTests(TestCase):

    def test_person_multiple_choice(self):
        """
        Verify that PersonModelMultipleChoice returns `full_name` and `profile_image_url` as choice label.
        """
        course_form = CustomCourseRunForm()
        person = PersonFactory()
        course_form.fields['staff'].queryset = Person.objects.all()
        course_form.fields['staff'].empty_label = None

        # we need to loop through choices because it is a ModelChoiceIterator
        for __, choice_label in course_form.fields['staff'].choices:
            expected = '<img src="{profile_image}"/><span>{full_name}</span>'.format(
                full_name=person.full_name,
                profile_image=person.profile_image_url
            )
            self.assertEqual(choice_label.strip(), expected)
