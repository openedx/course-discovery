from django.contrib.auth.models import Group
from django.urls import reverse

from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.publisher.api import views
from course_discovery.apps.publisher.choices import InternalUserRole
from course_discovery.apps.publisher.constants import INTERNAL_USER_GROUP_NAME
from course_discovery.apps.publisher.tests import JSON_CONTENT_TYPE, factories


class OrganizationGroupUserViewTests(APITestCase):

    def setUp(self):
        super().setUp()

        self.user = UserFactory.create(username="test_user", password=USER_PASSWORD)
        self.client.login(username=self.user.username, password=USER_PASSWORD)

        self.internal_user_group = Group.objects.get(name=INTERNAL_USER_GROUP_NAME)
        self.user.groups.add(self.internal_user_group)
        organization_extension = factories.OrganizationExtensionFactory()
        self.org_user1 = UserFactory.create(full_name="org user1")
        self.org_user2 = UserFactory.create(first_name='', last_name='', full_name='')
        organization_extension.group.user_set.add(*[self.org_user1, self.org_user2])
        self.organization = organization_extension.organization

    def query(self, org_id=None):
        if org_id is None:
            org_id = self.organization.id
        url = reverse('publisher:api:organization_group_users', kwargs={'pk': org_id})
        return self.client.get(path=url, content_type=JSON_CONTENT_TYPE)

    def assertExpectedUsers(self, response):
        self.assertEqual(response.status_code, 200)
        expected_results = [
            {
                "id": self.org_user1.id,
                "full_name": self.org_user1.full_name,
                "email": self.org_user1.email,
            },
            {
                "id": self.org_user2.id,
                "full_name": self.org_user2.username,
                "email": self.org_user2.email,
            }
        ]
        self.assertCountEqual(expected_results, response.json()['results'])

    def test_happy_path(self):
        """
        Verify that view returns list of users associated with the group related to given organization id with
        login users is associated with any publisher group.
        """
        response = self.query()
        self.assertExpectedUsers(response)

    def test_num_queries(self):
        view = views.OrganizationGroupUserView(kwargs={'pk': str(self.organization.id)})
        with self.assertNumQueries(2, threshold=0):  # one for Org Ext, one for users
            list(view.get_queryset())

    def test_get_organization_not_found(self):
        """
        Verify that view returns status=404 if organization is not found in OrganizationExtension.
        """
        response = self.query(org_id=0)
        self.assertEqual(response.status_code, 404)

    def test_get_organization_user_group_without_publisher_user_permissions(self):
        """
        Verify that endpoint returns a permission error with login users not associated
        with any publisher group.
        """
        self.user.groups.remove(self.internal_user_group)
        response = self.query()
        self.assertEqual(response.status_code, 403)

    def test_get_organization_by_uuid(self):
        """ Verify that endpoint accepts a UUID. """
        response = self.query(org_id=self.organization.uuid)
        self.assertExpectedUsers(response)


class OrganizationUserViewTests(APITestCase):

    def setUp(self):
        super().setUp()
        self.user = UserFactory.create(username="test_user", password=USER_PASSWORD)
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.internal_user_group = Group.objects.get(name=INTERNAL_USER_GROUP_NAME)
        self.user.groups.add(self.internal_user_group)
        self.expected_user = UserFactory()
        self.organization_extension = factories.OrganizationExtensionFactory()

    def query(self):
        url = reverse('publisher:api:organization_users')
        return self.client.get(path=url, content_type=JSON_CONTENT_TYPE)

    def test_repsonse_for_staff_user(self):
        self.organization_extension.organization.partner = self.site.partner
        self.organization_extension.organization.save()
        self.expected_user.groups.add(self.organization_extension.group)
        self.user.is_staff = True
        self.user.save()

        response = self.query()
        results = response.json().get('results')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].get('full_name'), self.expected_user.full_name)

    def test_response_for_non_staff_user(self):
        self.expected_user.groups.add(self.organization_extension.group)
        self.user.groups.add(self.organization_extension.group)

        response = self.query()
        results = response.json().get('results')
        self.assertEqual(len(results), 2)


class OrganizationUserRoleViewTests(APITestCase):
    def setUp(self):
        super().setUp()

        self.user = UserFactory.create(username="test_user", password=USER_PASSWORD)
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.internal_user_group = Group.objects.get(name=INTERNAL_USER_GROUP_NAME)
        self.user.groups.add(self.internal_user_group)
        self.pc_slug = InternalUserRole.ProjectCoordinator
        self.pm_slug = InternalUserRole.PartnerManager
        self.pub_slug = InternalUserRole.Publisher
        self.role = factories.OrganizationUserRoleFactory(user=self.user, role=self.pc_slug)
        self.organization = self.role.organization

    def query(self, org_id=None, param=None):
        if org_id is None:
            org_id = self.organization.id
        url = reverse('publisher:api:organization_user_roles', kwargs={'pk': org_id})
        if param:
            url += '?' + param
        return self.client.get(path=url, content_type=JSON_CONTENT_TYPE)

    def assertExpectedRoles(self, response, roles=None):
        self.assertEqual(response.status_code, 200)
        roles = roles or [self.role.role]
        self.assertListEqual(sorted(roles), sorted(role['role'] for role in response.json()['results']))

    def test_happy_path(self):
        """
        Verify that view returns list of roles associated with the given organization id.
        """
        response = self.query()
        self.assertExpectedRoles(response)

    def test_num_queries(self):
        view = views.OrganizationUserRoleView(kwargs={'pk': str(self.organization.id)})
        with self.assertNumQueries(1, threshold=0):
            list(view.get_queryset())

    def test_role_param(self):
        """
        Verify that view accepts a role query param.
        """
        factories.OrganizationUserRoleFactory(organization=self.organization, role=self.pub_slug)
        factories.OrganizationUserRoleFactory(organization=self.organization, role=self.pub_slug)
        factories.OrganizationUserRoleFactory(organization=self.organization, role=self.pm_slug)

        # Single role
        response = self.query(param='role=%s' % self.pm_slug)
        self.assertExpectedRoles(response, [self.pm_slug])

        # Two roles
        response = self.query(param='role=%s,%s' % (self.pm_slug, self.pub_slug))
        self.assertExpectedRoles(response, [self.pm_slug, self.pub_slug, self.pub_slug])

    def test_only_org_roles(self):
        """
        Verify that view only returns results for the given org.
        """
        factories.OrganizationUserRoleFactory(role=self.pub_slug)
        response = self.query()
        self.assertExpectedRoles(response)  # new role above won't be included

    def test_get_without_publisher_user_permissions(self):
        """
        Verify that endpoint returns a permission error with login users not associated
        with any publisher group.
        """
        self.user.groups.remove(self.internal_user_group)
        response = self.query()
        self.assertEqual(response.status_code, 403)

    def test_get_organization_by_uuid(self):
        """ Verify that endpoint accepts a UUID. """
        response = self.query(org_id=self.role.organization.uuid)
        self.assertExpectedRoles(response)
