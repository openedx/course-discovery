# pylint: disable=no-member
from django.db import IntegrityError
from django.test import TestCase
from guardian.shortcuts import assign_perm

from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.course_metadata.tests.mixins import MarketingSitePublisherTestMixin
from course_discovery.apps.publisher.choices import CourseRunStateChoices, CourseStateChoices, PublisherUserRole
from course_discovery.apps.publisher.models import CourseUserRole, OrganizationExtension, OrganizationUserRole
from course_discovery.apps.publisher.tests import factories


class CourseRunTests(TestCase):
    def test_str(self):
        """ Verify casting an instance to a string returns a string containing the course title and start date. """
        course_run = factories.CourseRunFactory()
        self.assertEqual(
            str(course_run),
            '{title}: {date}'.format(
                title=course_run.course.title, date=course_run.start
            )
        )


class CourseTests(TestCase):
    def setUp(self):
        super(CourseTests, self).setUp()
        self.org_extension_1 = factories.OrganizationExtensionFactory()
        self.org_extension_2 = factories.OrganizationExtensionFactory()

        self.course = factories.CourseFactory(organizations=[self.org_extension_1.organization])
        self.course2 = factories.CourseFactory(organizations=[self.org_extension_2.organization])

        self.user1 = UserFactory()
        self.user2 = UserFactory()

        self.user1.groups.add(self.org_extension_1.group)
        self.user2.groups.add(self.org_extension_2.group)

    def test_str(self):
        """ Verify casting an instance to a string returns a string containing the course title. """
        self.assertEqual(str(self.course), self.course.title)

    def test_assign_permission_organization_extension(self):
        """ Verify that permission can be assigned using the organization extension. """
        self.assert_user_cannot_view_course(self.user1, self.course, OrganizationExtension.VIEW_COURSE)
        self.assert_user_cannot_view_course(self.user2, self.course2, OrganizationExtension.VIEW_COURSE)

        self.course.organizations.add(self.org_extension_1.organization)
        self.course2.organizations.add(self.org_extension_2.organization)

        assign_perm(OrganizationExtension.VIEW_COURSE, self.org_extension_1.group, self.org_extension_1)
        assign_perm(OrganizationExtension.VIEW_COURSE, self.org_extension_2.group, self.org_extension_2)

        self.assert_user_can_view_course(self.user1, self.course, OrganizationExtension.VIEW_COURSE)
        self.assert_user_can_view_course(self.user2, self.course2, OrganizationExtension.VIEW_COURSE)

        self.assert_user_cannot_view_course(self.user1, self.course2, OrganizationExtension.VIEW_COURSE)
        self.assert_user_cannot_view_course(self.user2, self.course, OrganizationExtension.VIEW_COURSE)

        self.assertEqual(self.course.organizations.first().organization_extension.group, self.org_extension_1.group)
        self.assertEqual(self.course2.organizations.first().organization_extension.group, self.org_extension_2.group)

    @staticmethod
    def check_course_organization_permission(user, course, permission):
        return any(
            [
                user.has_perm(permission, org.organization_extension)
                for org in course.organizations.all()
            ]
        )

    def assert_user_cannot_view_course(self, user, course, permission):
        """ Asserts the user can NOT view the course. """
        self.assertFalse(CourseTests.check_course_organization_permission(user, course, permission))

    def assert_user_can_view_course(self, user, course, permission):
        """ Asserts the user can view the course. """
        self.assertTrue(CourseTests.check_course_organization_permission(user, course, permission))


class TestSeatModel(TestCase):
    def test_str(self):
        seat = factories.SeatFactory()
        assert str(seat) == '{course}: {type}'.format(course=seat.course_run.course.title, type=seat.type)


class UserAttributeTests(TestCase):
    def test_str(self):
        """ Verify casting an instance to a string returns a string containing the user name and
        current enable status. """
        user_attr = factories.UserAttributeFactory()
        self.assertEqual(
            str(user_attr),
            '{user}: {enable_email_notification}'.format(
                user=user_attr.user,
                enable_email_notification=user_attr.enable_email_notification
            )
        )


class OrganizationUserRoleTests(TestCase):
    def setUp(self):
        super(OrganizationUserRoleTests, self).setUp()
        self.org_user_role = factories.OrganizationUserRoleFactory(role=PublisherUserRole.ProjectCoordinator)

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
    def setUp(self):
        super(CourseUserRoleTests, self).setUp()
        self.course_user_role = factories.CourseUserRoleFactory(role=PublisherUserRole.ProjectCoordinator)

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
    def setUp(self):
        super(GroupOrganizationTests, self).setUp()
        self.organization_extension = factories.OrganizationExtensionFactory()
        self.group_2 = factories.GroupFactory()

    def test_str(self):
        """Verify that a GroupOrganization is properly converted to a str."""
        expected_str = '{organization}: {group}'.format(
            organization=self.organization_extension.organization, group=self.organization_extension.group
        )
        self.assertEqual(str(self.organization_extension), expected_str)

    def test_one_to_one_constraint(self):
        """ Verify that same group or organization have only one record."""

        with self.assertRaises(IntegrityError):
            OrganizationExtension.objects.create(
                group=self.group_2,
                organization=self.organization_extension.organization
            )


class CourseStateTests(TestCase):
    def test_str(self):
        """
        Verify casting an instance to a string returns a string containing the current state display name.
        """
        course_state = factories.CourseStateFactory(name=CourseStateChoices.Draft)
        self.assertEqual(str(course_state), course_state.get_name_display())


class CourseRunStateTests(MarketingSitePublisherTestMixin):
    def test_str(self):
        """
        Verify casting an instance to a string returns a string containing the current state display name.
        """
        course_run_state = factories.CourseRunStateFactory(name=CourseRunStateChoices.Draft)
        self.assertEqual(str(course_run_state), course_run_state.get_name_display())
