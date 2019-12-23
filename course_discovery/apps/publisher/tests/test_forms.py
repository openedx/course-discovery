import ddt
from django.core.exceptions import ValidationError
from django.test import TestCase

from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.publisher.choices import CourseRunStateChoices, PublisherUserRole
from course_discovery.apps.publisher.forms import (
    CourseRunStateAdminForm, CourseStateAdminForm, PublisherUserCreationForm
)
from course_discovery.apps.publisher.tests.factories import CourseFactory, CourseUserRoleFactory


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
