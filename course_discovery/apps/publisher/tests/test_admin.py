import ddt
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from guardian.shortcuts import get_group_perms

from course_discovery.apps.api.tests.mixins import SiteMixin
from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.course_metadata.tests.factories import OrganizationFactory
from course_discovery.apps.publisher.choices import PublisherUserRole
from course_discovery.apps.publisher.constants import (
    PARTNER_MANAGER_GROUP_NAME, PROJECT_COORDINATOR_GROUP_NAME, PUBLISHER_GROUP_NAME, REVIEWER_GROUP_NAME
)
from course_discovery.apps.publisher.models import OrganizationExtension
from course_discovery.apps.publisher.tests import factories
from course_discovery.apps.publisher.tests.factories import CourseFactory

USER_PASSWORD = 'password'


class OrganizationExtensionAdminTests(SiteMixin, TestCase):
    """ Tests for OrganizationExtensionAdmin."""

    def setUp(self):
        super(OrganizationExtensionAdminTests, self).setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.run_state = factories.CourseRunStateFactory()
        self.admin_page_url = reverse('admin:publisher_organizationextension_add')

    def test_organization_extension_permission(self):
        """
        Verify that required permissions assigned to OrganizationExtension object.
        """
        test_organization = OrganizationFactory()
        test_group = factories.GroupFactory()
        post_data = {'organization': test_organization.id, 'group': test_group.id}
        self.client.post(self.admin_page_url, data=post_data)

        organization_extension = OrganizationExtension.objects.get(organization=test_organization, group=test_group)

        course_team_permissions = [
            OrganizationExtension.VIEW_COURSE,
            OrganizationExtension.EDIT_COURSE,
            OrganizationExtension.VIEW_COURSE_RUN,
            OrganizationExtension.EDIT_COURSE_RUN
        ]
        self._assert_permissions(organization_extension, test_group, course_team_permissions)

        marketing_permissions = [
            OrganizationExtension.VIEW_COURSE,
            OrganizationExtension.EDIT_COURSE,
            OrganizationExtension.VIEW_COURSE_RUN
        ]
        self._assert_permissions(
            organization_extension, Group.objects.get(name=REVIEWER_GROUP_NAME), marketing_permissions
        )

        pc_permissions = [
            OrganizationExtension.VIEW_COURSE,
            OrganizationExtension.EDIT_COURSE_RUN,
            OrganizationExtension.VIEW_COURSE_RUN
        ]
        self._assert_permissions(
            organization_extension, Group.objects.get(name=PROJECT_COORDINATOR_GROUP_NAME), pc_permissions
        )

    def _assert_permissions(self, organization_extension, group, expected_permissions):
        permissions = get_group_perms(group, organization_extension)
        self.assertEqual(sorted(permissions), sorted(expected_permissions))


@ddt.ddt
class OrganizationUserRoleAdminTests(SiteMixin, TestCase):
    """ Tests for OrganizationUserRoleAdmin."""

    def setUp(self):
        super(OrganizationUserRoleAdminTests, self).setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.admin_page_url = reverse('admin:publisher_organizationuserrole_add')

        self.organization = OrganizationFactory()

        self.course1 = CourseFactory(organizations=[self.organization])
        self.course2 = CourseFactory(organizations=[self.organization])

    @ddt.data(
        (PublisherUserRole.MarketingReviewer, REVIEWER_GROUP_NAME),
        (PublisherUserRole.ProjectCoordinator, PROJECT_COORDINATOR_GROUP_NAME),
        (PublisherUserRole.Publisher, PUBLISHER_GROUP_NAME),
        (PublisherUserRole.PartnerManager, PARTNER_MANAGER_GROUP_NAME)
    )
    @ddt.unpack
    def test_organization_user_role_groups(self, role, group_name):
        """
        Verify that a group is assigned to user according to its role upon OrganizationUserRole creation
        and create course users also.
        """
        test_user = UserFactory()
        post_data = {
            'organization': self.organization.id, 'user': test_user.id, 'role': role
        }

        self.client.post(self.admin_page_url, data=post_data)

        # Verify that user is added to the group.
        self.assertIn(Group.objects.get(name=group_name), test_user.groups.all())

        self.assertEqual(self.course1.course_user_roles.filter(role=role).count(), 1)
        self.assertEqual(self.course2.course_user_roles.filter(role=role).count(), 1)
        self.assertEqual(self.course2.course_user_roles.filter(role=role).first().user, test_user)

    def test_save_method_add_course_user_roles(self):
        """
        Verify that save method will not create the duplicate course user roles.
        """
        # for course 3 add course roles
        user = UserFactory()
        course3 = CourseFactory(organizations=[self.organization])
        factories.CourseUserRoleFactory(course=course3, role=PublisherUserRole.MarketingReviewer, user=user)

        # for course 4 add course roles
        project_coordinator = UserFactory()
        course4 = CourseFactory(organizations=[self.organization])
        factories.CourseUserRoleFactory(course=course4, role=PublisherUserRole.ProjectCoordinator,
                                        user=project_coordinator)

        test_user = UserFactory()
        post_data = {
            'organization': self.organization.id, 'user': test_user.id, 'role': PublisherUserRole.MarketingReviewer
        }
        self.client.post(self.admin_page_url, data=post_data)

        # for course-4 course-user-role does not change
        self.assertTrue(
            course4.course_user_roles.filter(role=PublisherUserRole.ProjectCoordinator,
                                             user=project_coordinator).exists()
        )

        # for course-3 course-user-role also changes to test_user
        self.assertTrue(course3.course_user_roles.filter(role=PublisherUserRole.MarketingReviewer,
                                                         user=test_user).exists())

        self.assertTrue(
            self.course1.course_user_roles.filter(role=PublisherUserRole.MarketingReviewer, user=test_user).exists()
        )
        self.assertTrue(
            self.course2.course_user_roles.filter(role=PublisherUserRole.MarketingReviewer, user=test_user).exists()
        )
