""" Tests publisher.utils"""
from datetime import datetime

import ddt
from django.contrib.auth.models import Group
from django.test import RequestFactory, TestCase
from django.urls import reverse
from guardian.shortcuts import assign_perm
from mock import Mock

from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.course_metadata.tests import factories as cm_factories
from course_discovery.apps.publisher.constants import (
    ADMIN_GROUP_NAME, INTERNAL_USER_GROUP_NAME, PROJECT_COORDINATOR_GROUP_NAME, REVIEWER_GROUP_NAME
)
from course_discovery.apps.publisher.mixins import (
    check_course_organization_permission, check_roles_access, publisher_user_required
)
from course_discovery.apps.publisher.models import OrganizationExtension
from course_discovery.apps.publisher.tests import factories
from course_discovery.apps.publisher.utils import (
    find_discovery_course, get_internal_users, has_role_for_course, is_course_on_old_publisher,
    is_email_notification_enabled, is_internal_user, is_on_old_publisher, is_project_coordinator_user, is_publisher_admin,
    is_publisher_course_on_old_publisher, is_publisher_user, make_bread_crumbs, parse_datetime_field
)


@ddt.ddt
class PublisherUtilsTests(TestCase):
    """ Tests for the publisher utils. """

    def setUp(self):
        super(PublisherUtilsTests, self).setUp()
        self.user = UserFactory()
        self.organization_extension = factories.OrganizationExtensionFactory()
        self.course = factories.CourseFactory(organizations=[self.organization_extension.organization])
        self.admin_group = Group.objects.get(name=ADMIN_GROUP_NAME)
        self.internal_user_group = Group.objects.get(name=INTERNAL_USER_GROUP_NAME)

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
        user_attribute.save()

        # Verify that email notifications are disabled for the user
        self.assertEqual(is_email_notification_enabled(self.user), False)

    def test_is_publisher_admin(self):
        """
        Verify the function returns a boolean indicating if the user is a member of the administrative group.
        """
        self.assertFalse(self.user.groups.filter(name=ADMIN_GROUP_NAME).exists())
        self.assertFalse(is_publisher_admin(self.user))

        admin_group = Group.objects.get(name=ADMIN_GROUP_NAME)
        self.user.groups.add(admin_group)
        self.assertTrue(is_publisher_admin(self.user))

    def test_is_internal_user(self):
        """
        Verify the function returns a boolean indicating if the user is a member of the internal user group.
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

    def test_is_project_coordinator_user(self):
        """
        Verify the function returns a boolean indicating if the user is a member of the project coordinator group.
        """
        self.assertFalse(is_project_coordinator_user(self.user))

        project_coordinator_group = Group.objects.get(name=PROJECT_COORDINATOR_GROUP_NAME)
        self.user.groups.add(project_coordinator_group)
        self.assertTrue(is_project_coordinator_user(self.user))

    def test_check_roles_access_with_admin(self):
        """ Verify the function returns True if user is in an admin group, otherwise False. """
        self.assertFalse(check_roles_access(self.user))
        self.user.groups.add(self.admin_group)
        self.assertTrue(check_roles_access(self.user))

    def test_check_roles_access_with_internal_user(self):
        """ Verify the function returns True if user is in an internal group, otherwise False. """
        self.assertFalse(check_roles_access(self.user))
        self.user.groups.add(self.internal_user_group)
        self.assertTrue(check_roles_access(self.user))

    def test_check_organization_permission_without_org(self):
        """
        Verify the function returns True if the user has organization permission on given course, otherwise False.
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
        """
        Verify the function returns a boolean indicating if the user
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
        """
        Verify the function returns True if the user has organization permission on given course, otherwise False.
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
        """
        Verify the function returns a boolean indicating if the user is part of any publisher app group.
        """
        self.assertFalse(is_publisher_user(self.user))
        self.user.groups.add(Group.objects.get(name=REVIEWER_GROUP_NAME))
        self.assertTrue(is_publisher_user(self.user))

    def test_require_is_publisher_user_without_group(self):
        """
        Verify that decorator returns the error message if user is not part of any publisher group.
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
        Verify that decorator works fine with user is part of publisher app group.
        """
        func = Mock()
        decorated_func = publisher_user_required(func)
        request = RequestFactory()
        request.user = self.user
        self.user.groups.add(self.internal_user_group)

        decorated_func(request, self.user)
        self.assertTrue(func.called)

    def test_make_bread_crumbs(self):
        """ Verify the function parses the list of tuples and returns a list of corresponding dicts."""
        links = [(reverse('publisher:publisher_courses_new'), 'Courses'), (None, 'Testing')]
        self.assertEqual(
            [{'url': '/publisher/courses/new/', 'slug': 'Courses'}, {'url': None, 'slug': 'Testing'}],
            make_bread_crumbs(links)
        )

    def test_has_role_for_course(self):
        """
        Verify the function returns a boolean indicating if the user has a role for course.
        """

        self.assertFalse(has_role_for_course(self.course, self.user))
        factories.CourseUserRoleFactory(course=self.course, user=self.user)
        self.assertTrue(has_role_for_course(self.course, self.user))

    @ddt.data(
        'april 20, 2017',
        'aug 20 2019',
        '2020 may 20',
        '09 04 2018',
        'jan 20 2020'
    )
    def test_parse_datetime_field(self, date):
        """ Verify that function return datetime after parsing different possible date format. """
        parsed_date = parse_datetime_field(date)
        self.assertTrue(isinstance(parsed_date, datetime))

    @ddt.data(
        None,
        'jan 20 20203'
        'invalid-date-string'
        'jan 20'
    )
    def test_parse_datetime_field_with_invalid_date_format(self, invalid_date):
        """ Verify that function return None if date string does not match any possible date format. """
        parsed_date = parse_datetime_field(invalid_date)
        self.assertIsNone(parsed_date)

    def test_find_discovery_course(self):
        cm_run1 = cm_factories.CourseRunFactory(course__partner=self.course.partner)
        cm_run2 = cm_factories.CourseRunFactory(course__partner=self.course.partner)
        pub_run1 = factories.CourseRunFactory(course=self.course, lms_course_id=cm_run1.key)
        pub_run2 = factories.CourseRunFactory(course=self.course, lms_course_id=cm_run2.key)
        pub_run_no_id = factories.CourseRunFactory(course=self.course)
        pub_run_no_siblings = factories.CourseRunFactory()

        assert find_discovery_course(pub_run1) == cm_run1.course
        assert find_discovery_course(pub_run2) == cm_run2.course
        assert find_discovery_course(pub_run_no_id) == cm_run2.course  # Most recent sibling run's course
        assert find_discovery_course(pub_run_no_siblings) is None

    def test_is_on_old_publisher(self):
        def staff_user_always_true(user):
            user.is_staff = True
            self.assertTrue(is_on_old_publisher(user))
            user.is_staff = False

        # When no ORGS_ON_OLD_PUBLISHER list present
        self.assertFalse(is_on_old_publisher(self.user))

        with self.settings(ORGS_ON_OLD_PUBLISHER=self.organization_extension.organization.key):
            # When ORGS_ON_OLD_PUBLISHER list present and user has no orgs
            self.assertFalse(is_on_old_publisher(self.user))
            staff_user_always_true(self.user)

        self.user.groups.add(self.organization_extension.group)

        with self.settings(ORGS_ON_OLD_PUBLISHER=self.organization_extension.organization.key):
            # When ORGS_ON_OLD_PUBLISHER list present and user belongs to an org in the list
            self.assertTrue(is_on_old_publisher(self.user))
            staff_user_always_true(self.user)

        with self.settings(ORGS_ON_OLD_PUBLISHER='example-key'):
            # When ORGS_ON_OLD_PUBLISHER list present and user belongs to org not in the list
            self.assertFalse(is_on_old_publisher(self.user))

        with self.settings(ORGS_ON_OLD_PUBLISHER=self.organization_extension.organization.key):
            org_ext = factories.OrganizationExtensionFactory()
            self.user.groups.add(self.organization_extension.group)
            self.user.groups.add(org_ext.group)
            # When ORGS_ON_OLD_PUBLISHER list present and user belongs to orgs both on and off the list
            self.assertTrue(is_on_old_publisher(self.user))

    def test_course_is_on_old_publisher(self):
        org = self.organization_extension.organization
        course = cm_factories.CourseFactory()

        # When no ORGS_ON_OLD_PUBLISHER list present
        self.assertFalse(is_course_on_old_publisher(course))

        with self.settings(ORGS_ON_OLD_PUBLISHER=org.key):
            # When ORGS_ON_OLD_PUBLISHER list present and course has no orgs
            self.assertFalse(is_course_on_old_publisher(course))

        course.authoring_organizations.add(org)

        with self.settings(ORGS_ON_OLD_PUBLISHER=org.key):
            # When ORGS_ON_OLD_PUBLISHER list present and course is authored by an org in the list
            self.assertTrue(is_course_on_old_publisher(course))

        with self.settings(ORGS_ON_OLD_PUBLISHER='example-key'):
            # When ORGS_ON_OLD_PUBLISHER list present and course is authored by an org not in the list
            self.assertFalse(is_course_on_old_publisher(course))

        with self.settings(ORGS_ON_OLD_PUBLISHER=org.key):
            org2 = cm_factories.OrganizationFactory()
            course.authoring_organizations.add(org2)
            # When ORGS_ON_OLD_PUBLISHER list present and course is authored by orgs both on and off the list
            self.assertTrue(is_course_on_old_publisher(course))

    def test_publisher_course_on_old_publisher(self):
        org = self.organization_extension.organization
        course = factories.CourseFactory()

        # When no ORGS_ON_OLD_PUBLISHER list present
        self.assertFalse(is_publisher_course_on_old_publisher(course))

        with self.settings(ORGS_ON_OLD_PUBLISHER=org.key):
            # When ORGS_ON_OLD_PUBLISHER list present and course has no orgs
            self.assertFalse(is_publisher_course_on_old_publisher(course))

        course.organizations.add(org)

        with self.settings(ORGS_ON_OLD_PUBLISHER=org.key):
            # When ORGS_ON_OLD_PUBLISHER list present and course is authored by an org in the list
            self.assertTrue(is_publisher_course_on_old_publisher(course))

        with self.settings(ORGS_ON_OLD_PUBLISHER='example-key'):
            # When ORGS_ON_OLD_PUBLISHER list present and course is authored by an org not in the list
            self.assertFalse(is_publisher_course_on_old_publisher(course))

        with self.settings(ORGS_ON_OLD_PUBLISHER=org.key):
            org2 = cm_factories.OrganizationFactory()
            course.organizations.add(org2)
            # When ORGS_ON_OLD_PUBLISHER list present and course is authored by orgs both on and off the list
            self.assertTrue(is_publisher_course_on_old_publisher(course))
