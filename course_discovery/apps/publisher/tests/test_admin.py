from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from guardian.shortcuts import get_group_perms

from course_discovery.apps.api.tests.mixins import SiteMixin
from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.course_metadata.tests.factories import OrganizationFactory
from course_discovery.apps.publisher.constants import PROJECT_COORDINATOR_GROUP_NAME, REVIEWER_GROUP_NAME
from course_discovery.apps.publisher.models import OrganizationExtension
from course_discovery.apps.publisher.tests import factories

USER_PASSWORD = 'password'


class OrganizationExtensionAdminTests(SiteMixin, TestCase):
    """ Tests for OrganizationExtensionAdmin."""

    def setUp(self):
        super().setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.client.login(username=self.user.username, password=USER_PASSWORD)
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
