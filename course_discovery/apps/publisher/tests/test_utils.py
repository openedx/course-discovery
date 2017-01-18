""" Tests publisher.utils"""
import ddt

from django.contrib.auth.models import Group
from django.core.urlresolvers import reverse
from django.test import TestCase, RequestFactory
from mock import Mock

from guardian.shortcuts import assign_perm
from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.publisher.constants import (
    REVIEWER_GROUP_NAME, ADMIN_GROUP_NAME, INTERNAL_USER_GROUP_NAME,
    PARTNER_COORDINATOR_GROUP_NAME
)
from course_discovery.apps.publisher.mixins import (
    check_course_organization_permission, check_roles_access,
    publisher_user_required
)
from course_discovery.apps.publisher.models import OrganizationExtension
from course_discovery.apps.publisher.tests import factories
from course_discovery.apps.publisher.utils import (
    is_email_notification_enabled, is_publisher_admin, is_internal_user,
    get_internal_users, is_partner_coordinator_user, is_publisher_user,
    make_bread_crumbs
)


@ddt.ddt
class PublisherUtilsTests(TestCase):
    """ Tests for the publisher utils. """

    def setUp(self):
        super(PublisherUtilsTests, self).setUp()
        self.user = UserFactory()
        self.course = factories.CourseFactory()
        self.admin_group = Group.objects.get(name=ADMIN_GROUP_NAME)
        self.internal_user_group = Group.objects.get(name=INTERNAL_USER_GROUP_NAME)
        self.organization_extension = factories.OrganizationExtensionFactory()
        self.course.organizations.add(self.organization_extension.organization)

    def test_email_notification_enabled_by_default(self):
        """ Test email notification is enabled for the user by default."""

        self.assertFalse(hasattr(self.user, 'attributes'))

        # Verify email notifications are enabled for user without associated attributes
        self.assertEqual(is_email_notification_enabled(self.user), True)

    def test_is_email_notification_enabled(self):
        """ Test email notification enabled/disabled for the user."""

        user_attribute = factories.UserAttributeFactory(user=self.user)

        # Verify email notifications are enabled for user with associated attributes,
        # but no explicit value set for the enable_email_notification attribute
        self.assertEqual(is_email_notification_enabled(self.user), True)

        # Disabled email notification
        user_attribute.enable_email_notification = False
        user_attribute.save()  # pylint: disable=no-member

        # Verify that email notifications are disabled for the user
        self.assertEqual(is_email_notification_enabled(self.user), False)

    def test_is_publisher_admin(self):
        """ Verify the function returns a boolean indicating if the user
        is a member of the administrative group.
        """
        self.assertFalse(self.user.groups.filter(name=ADMIN_GROUP_NAME).exists())
        self.assertFalse(is_publisher_admin(self.user))

        admin_group = Group.objects.get(name=ADMIN_GROUP_NAME)
        self.user.groups.add(admin_group)
        self.assertTrue(is_publisher_admin(self.user))

    def test_is_internal_user(self):
        """ Verify the function returns a boolean indicating if the user
        is a member of the internal user group.
        """
        self.assertFalse(is_internal_user(self.user))

        internal_user_group = Group.objects.get(name=INTERNAL_USER_GROUP_NAME)
        self.user.groups.add(internal_user_group)
        self.assertTrue(is_internal_user(self.user))

    def test_get_internal_user(self):
        """ Verify the function returns all internal users. """
        internal_user_group = Group.objects.get(name=INTERNAL_USER_GROUP_NAME)
        self.assertEqual(get_internal_users(), [])

        self.user.groups.add(internal_user_group)
        self.assertEqual(get_internal_users(), [self.user])

    def test_is_partner_coordinator_user(self):
        """ Verify the function returns a boolean indicating if the user
        is a member of the partner coordinator group.
        """
        self.assertFalse(is_partner_coordinator_user(self.user))

        partner_coordinator_group = Group.objects.get(name=PARTNER_COORDINATOR_GROUP_NAME)
        self.user.groups.add(partner_coordinator_group)
        self.assertTrue(is_partner_coordinator_user(self.user))

    def test_check_roles_access_with_admin(self):
        """ Verify the function returns a boolean indicating if the user
        access role wise.
        """
        self.assertFalse(check_roles_access(self.user))
        self.user.groups.add(self.admin_group)
        self.assertTrue(check_roles_access(self.user))

    def test_check_roles_access_with_internal_user(self):
        """ Verify the function returns a boolean indicating if the user
        access role wise.
        """
        self.assertFalse(check_roles_access(self.user))
        self.user.groups.add(self.internal_user_group)
        self.assertTrue(check_roles_access(self.user))

    def test_check_organization_permission_without_org(self):
        """ Verify the function returns a boolean indicating if the user has
        organization permission on given course.
        """
        self.assertFalse(
            check_course_organization_permission(self.user, self.course, OrganizationExtension.VIEW_COURSE)
        )

        self.user.groups.add(self.organization_extension.group)
        assign_perm(
            OrganizationExtension.VIEW_COURSE, self.organization_extension.group, self.organization_extension
        )

        self.assertTrue(
            check_course_organization_permission(self.user, self.course, OrganizationExtension.VIEW_COURSE)
        )

    def test_check_user_access_with_roles(self):
        """ Verify the function returns a boolean indicating if the user
        organization permission on given course or user is internal or admin user.
        """
        self.assertFalse(check_roles_access(self.user))
        self.user.groups.add(self.admin_group)
        self.assertTrue(check_roles_access(self.user))
        self.user.groups.remove(self.admin_group)
        self.assertFalse(check_roles_access(self.user))
        self.user.groups.add(self.internal_user_group)
        self.assertTrue(check_roles_access(self.user))

    def test_check_user_access_with_permission(self):
        """ Verify the function returns a boolean indicating if the user
        has view permission on organization
        """
        self.assertFalse(
            check_course_organization_permission(self.user, self.course, OrganizationExtension.VIEW_COURSE)
        )

        self.user.groups.add(self.organization_extension.group)
        assign_perm(
            OrganizationExtension.VIEW_COURSE, self.organization_extension.group, self.organization_extension
        )

        self.assertTrue(
            check_course_organization_permission(self.user, self.course, OrganizationExtension.VIEW_COURSE)
        )

    def test_is_publisher_user(self):
        """ Verify the function returns a boolean indicating if the user
        is part of any publisher app group.
        """
        self.assertFalse(is_publisher_user(self.user))
        self.user.groups.add(Group.objects.get(name=REVIEWER_GROUP_NAME))
        self.assertTrue(is_publisher_user(self.user))

    def test_require_is_publisher_user_without_group(self):
        """
        Verify that decorator returns the error message if user is not part
        of any publisher group.
        """
        func = Mock()
        decorated_func = publisher_user_required(func)
        request = RequestFactory()
        request.user = self.user

        response = decorated_func(request, self.user)
        self.assertContains(response, "Must be Publisher user to perform this action.", status_code=403)
        self.assertFalse(func.called)

    def test_is_publisher_user_with_publisher_group(self):
        """
        Verify that decorator works fine with user is part of publisher
        app group.
        """
        func = Mock()
        decorated_func = publisher_user_required(func)
        request = RequestFactory()
        request.user = self.user
        self.user.groups.add(self.internal_user_group)

        decorated_func(request, self.user)
        self.assertTrue(func.called)

    def test_make_bread_crumbs(self):
        """ Verify the function parse the list of tuple and returns list of dicts."""
        links = [(reverse('publisher:publisher_courses_new'), 'Courses'), (None, 'Testing')]
        self.assertEqual(
            [{'url': '/publisher/courses/new/', 'slug': 'Courses'}, {'url': None, 'slug': 'Testing'}],
            make_bread_crumbs(links)
        )
