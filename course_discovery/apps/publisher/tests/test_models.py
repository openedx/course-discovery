from django.db import IntegrityError
from django.test import TestCase

from course_discovery.apps.publisher.choices import InternalUserRole
from course_discovery.apps.publisher.models import OrganizationExtension, OrganizationUserRole
from course_discovery.apps.publisher.tests import factories


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
        super().setUp()
        self.org_user_role = factories.OrganizationUserRoleFactory(role=InternalUserRole.ProjectCoordinator)

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


class GroupOrganizationTests(TestCase):
    def setUp(self):
        super().setUp()
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
