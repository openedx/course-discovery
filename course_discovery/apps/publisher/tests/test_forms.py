from django.test import TestCase

from course_discovery.apps.core.models import User
from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.publisher.forms import CustomCourseForm


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
