# pylint: disable=no-member
import ddt
from django.db import IntegrityError
from django.core.urlresolvers import reverse
from django.test import TestCase
from django_fsm import TransitionNotAllowed
from guardian.shortcuts import get_groups_with_perms

from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.publisher.choices import PublisherUserRole
from course_discovery.apps.publisher.models import (
    State, Course, CourseUserRole, GroupOrganization, OrganizationUserRole
)
from course_discovery.apps.publisher.tests import factories


@ddt.ddt
class CourseRunTests(TestCase):
    """ Tests for the publisher `CourseRun` model. """

    @classmethod
    def setUpClass(cls):
        super(CourseRunTests, cls).setUpClass()
        cls.course_run = factories.CourseRunFactory()

    def test_str(self):
        """ Verify casting an instance to a string returns a string containing the course title and start date. """
        self.assertEqual(
            str(self.course_run),
            '{title}: {date}'.format(
                title=self.course_run.course.title, date=self.course_run.start
            )
        )

    def test_post_back_url(self):
        self.assertEqual(
            self.course_run.post_back_url,
            reverse('publisher:publisher_course_runs_edit', kwargs={'pk': self.course_run.id})
        )

    @ddt.unpack
    @ddt.data(
        (State.DRAFT, State.NEEDS_REVIEW),
        (State.NEEDS_REVIEW, State.NEEDS_FINAL_APPROVAL),
        (State.NEEDS_FINAL_APPROVAL, State.FINALIZED),
        (State.FINALIZED, State.PUBLISHED),
        (State.PUBLISHED, State.DRAFT),
    )
    def test_workflow_change_state(self, source_state, target_state):
        """ Verify that we can change the workflow states according to allowed transition. """
        self.assertEqual(self.course_run.state.name, source_state)
        self.course_run.change_state(target=target_state)
        self.assertEqual(self.course_run.state.name, target_state)

    def test_workflow_change_state_not_allowed(self):
        """ Verify that we can't change the workflow state from `DRAFT` to `PUBLISHED` directly. """
        self.assertEqual(self.course_run.state.name, State.DRAFT)
        with self.assertRaises(TransitionNotAllowed):
            self.course_run.change_state(target=State.PUBLISHED)


class CourseTests(TestCase):
    """ Tests for the publisher `Course` model. """

    def setUp(self):
        super(CourseTests, self).setUp()
        self.course = factories.CourseFactory()
        self.course2 = factories.CourseFactory()

        self.user1 = UserFactory()
        self.user2 = UserFactory()
        self.user3 = UserFactory()

        self.group_organization_1 = factories.GroupOrganizationFactory()
        self.group_organization_2 = factories.GroupOrganizationFactory()

        self.user1.groups.add(self.group_organization_1.group)
        self.user2.groups.add(self.group_organization_2.group)

        self.course.organizations.add(self.group_organization_1.organization)
        self.course2.organizations.add(self.group_organization_2.organization)

    def test_str(self):
        """ Verify casting an instance to a string returns a string containing the course title. """
        self.assertEqual(str(self.course), self.course.title)

    def test_post_back_url(self):
        self.assertEqual(
            self.course.post_back_url,
            reverse('publisher:publisher_courses_edit', kwargs={'pk': self.course.id})
        )

    def test_assign_permission_by_group(self):
        """ Verify that permission can be assigned using the group. """
        self.assert_user_cannot_view_course(self.user1, self.course)
        self.assert_user_cannot_view_course(self.user2, self.course2)

        self.course.assign_permission_by_group(self.group_organization_1.group)
        self.course2.assign_permission_by_group(self.group_organization_2.group)

        self.assert_user_can_view_course(self.user1, self.course)
        self.assert_user_can_view_course(self.user2, self.course2)

        self.assert_user_cannot_view_course(self.user1, self.course2)
        self.assert_user_cannot_view_course(self.user2, self.course)

        self.assertEqual(self.course.group_organization.group, self.group_organization_1.group)
        self.assertEqual(self.course2.group_organization.group, self.group_organization_2.group)

    def assert_user_cannot_view_course(self, user, course):
        """ Asserts the user can NOT view the course. """
        self.assertFalse(user.has_perm(Course.VIEW_PERMISSION, course))

    def assert_user_can_view_course(self, user, course):
        """ Asserts the user can view the course. """
        self.assertTrue(user.has_perm(Course.VIEW_PERMISSION, course))

    def test_group_organization(self):
        """ Verify the method returns group-organization object."""
        self.assertEqual(factories.CourseFactory().group_organization, None)

        self.assertEqual(self.course.group_organization, self.group_organization_1)
        self.assertEqual(self.course2.group_organization, self.group_organization_2)

    def test_group_by_permission(self):
        """ Verify the method returns groups permitted to access the course."""
        self.assertFalse(get_groups_with_perms(self.course))
        self.course.assign_permission_by_group(self.group_organization_1.group)
        self.assertEqual(get_groups_with_perms(self.course)[0], self.group_organization_1.group)

    def test_get_group_users_emails(self):
        """ Verify the method returns the email addresses of users who are
        permitted to access the course AND have not disabled email notifications.
        """
        self.user3.groups.add(self.group_organization_1.group)
        self.course.assign_permission_by_group(self.group_organization_1.group)
        self.assertListEqual(self.course.get_group_users_emails(), [self.user1.email, self.user3.email])

        # The email addresses of users who have disabled email notifications should NOT be returned.
        factories.UserAttributeFactory(user=self.user1, enable_email_notification=False)
        self.assertListEqual(self.course.get_group_users_emails(), [self.user3.email])

    def test_keywords_data(self):
        """ Verify that the property returns the keywords as comma separated string. """
        self.assertFalse(self.course.keywords_data)
        self.course.keywords.add('abc')
        self.assertEqual(self.course.keywords_data, 'abc')

        self.course.keywords.add('def')
        self.assertIn('abc', self.course.keywords_data)
        self.assertIn('def', self.course.keywords_data)


class SeatTests(TestCase):
    """ Tests for the publisher `Seat` model. """

    def setUp(self):
        super(SeatTests, self).setUp()
        self.seat = factories.SeatFactory()

    def test_str(self):
        """ Verify casting an instance to a string returns a string containing the course title and seat type. """
        self.assertEqual(
            str(self.seat),
            '{course}: {type}'.format(
                course=self.seat.course_run.course.title, type=self.seat.type
            )
        )

    def test_post_back_url(self):
        self.assertEqual(
            self.seat.post_back_url,
            reverse('publisher:publisher_seats_edit', kwargs={'pk': self.seat.id})
        )


class StateTests(TestCase):
    """ Tests for the publisher `State` model. """

    def setUp(self):
        super(StateTests, self).setUp()
        self.state = factories.StateFactory()

    def test_str(self):
        """ Verify casting an instance to a string returns a string containing the current state display name. """
        self.assertEqual(
            str(self.state),
            self.state.get_name_display()
        )


class UserAttributeTests(TestCase):
    """ Tests for the publisher `UserAttribute` model. """

    def setUp(self):
        super(UserAttributeTests, self).setUp()
        self.user_attr = factories.UserAttributeFactory()

    def test_str(self):
        """ Verify casting an instance to a string returns a string containing the user name and
        current enable status. """
        self.assertEqual(
            str(self.user_attr),
            '{user}: {enable_email_notification}'.format(
                user=self.user_attr.user,
                enable_email_notification=self.user_attr.enable_email_notification
            )
        )


class OrganizationUserRoleTests(TestCase):
    """Tests of the OrganizationUserRole model."""

    def setUp(self):
        super(OrganizationUserRoleTests, self).setUp()
        self.org_user_role = factories.OrganizationUserRoleFactory(role=PublisherUserRole.PartnerCoordinator)

    def test_str(self):
        """Verify that a OrganizationUserRole is properly converted to a str."""
        self.assertEqual(
            str(self.org_user_role), '{organization}: {user}: {role}'.format(
                organization=self.org_user_role.organization,
                user=self.org_user_role.user,
                role=self.org_user_role.role
            )
        )

    def test_unique_constraint(self):
        """ Verify a user cannot have multiple rows for the same organization-role combination. """
        with self.assertRaises(IntegrityError):
            OrganizationUserRole.objects.create(
                user=self.org_user_role.user,
                organization=self.org_user_role.organization,
                role=self.org_user_role.role
            )


class CourseUserRoleTests(TestCase):
    """Tests of the CourseUserRole model."""

    def setUp(self):
        super(CourseUserRoleTests, self).setUp()
        self.course_user_role = factories.CourseUserRoleFactory(role=PublisherUserRole.PartnerCoordinator)

    def test_str(self):
        """Verify that a CourseUserRole is properly converted to a str."""
        expected_str = '{course}: {user}: {role}'.format(
            course=self.course_user_role.course, user=self.course_user_role.user, role=self.course_user_role.role
        )
        self.assertEqual(str(self.course_user_role), expected_str)

    def test_unique_constraint(self):
        """ Verify a user cannot have multiple rows for the same course-role combination."""
        with self.assertRaises(IntegrityError):
            CourseUserRole.objects.create(
                course=self.course_user_role.course, user=self.course_user_role.user, role=self.course_user_role.role
            )


class GroupOrganizationTests(TestCase):
    """Tests of the GroupOrganization model."""

    def setUp(self):
        super(GroupOrganizationTests, self).setUp()
        self.group_organization = factories.GroupOrganizationFactory()
        self.group_2 = factories.GroupFactory()

    def test_str(self):
        """Verify that a GroupOrganization is properly converted to a str."""
        expected_str = '{organization}: {group}'.format(
            organization=self.group_organization.organization, group=self.group_organization.group
        )
        self.assertEqual(str(self.group_organization), expected_str)

    def test_one_to_one_constraint(self):
        """ Verify that same group or organization have only one record."""

        with self.assertRaises(IntegrityError):
            GroupOrganization.objects.create(
                group=self.group_2,
                organization=self.group_organization.organization
            )
