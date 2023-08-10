import uuid

from django.urls import reverse
from guardian.shortcuts import assign_perm

from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase, SerializationMixin
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.tests.factories import Organization, OrganizationFactory
from course_discovery.apps.publisher.models import OrganizationExtension
from course_discovery.apps.publisher.tests import factories as publisher_factories


class OrganizationViewSetTests(SerializationMixin, APITestCase):
    list_path = reverse('api:v1:organization-list')

    def setUp(self):
        super().setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.non_staff_user = UserFactory()
        self.request.user = self.user
        self.client.login(username=self.user.username, password=USER_PASSWORD)

    def test_authentication(self):
        """ Verify the endpoint requires the user to be authenticated. """
        response = self.client.get(self.list_path)
        self.assertEqual(response.status_code, 200)

        self.client.logout()
        response = self.client.get(self.list_path)
        self.assertEqual(response.status_code, 401)

    def assert_response_data_valid(self, response, organizations, many=True):
        """ Asserts the response data (only) contains the expected organizations. """
        actual = response.data
        serializer_data = self.serialize_organization(organizations, many=many)
        if many:
            actual = actual['results']

        self.assertCountEqual(actual, serializer_data)

    def assert_list_uuid_filter(self, organizations, expected_query_count):
        """ Asserts the list endpoint supports filtering by UUID. """
        organizations = sorted(organizations, key=lambda o: o.created)
        with self.assertNumQueries(expected_query_count):
            uuids = ','.join([organization.uuid.hex for organization in organizations])
            url = f'{self.list_path}?uuids={uuids}'
            response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assert_response_data_valid(response, organizations)

    def assert_list_tag_filter(self, organizations, tags, expected_query_count=7):
        """ Asserts the list endpoint supports filtering by tags. """
        with self.assertNumQueries(expected_query_count):
            tags = ','.join(tags)
            url = f'{self.list_path}?tags={tags}'
            response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assert_response_data_valid(response, organizations)

    def test_list(self):
        """ Verify the endpoint returns a list of all organizations. """
        OrganizationFactory.create_batch(3, partner=self.partner)

        with self.assertNumQueries(7):
            response = self.client.get(self.list_path)

        self.assertEqual(response.status_code, 200)
        self.assert_response_data_valid(response, Organization.objects.all())

    def test_list_not_staff(self):
        """ Verify the endpoint returns a list of all organizations. """
        org1 = OrganizationFactory.create(partner=self.partner)
        org2 = OrganizationFactory.create(partner=self.partner)
        OrganizationFactory.create(partner=self.partner)

        extension1 = publisher_factories.OrganizationExtensionFactory(organization=org1)
        publisher_factories.OrganizationExtensionFactory(organization=org2)
        assign_perm(OrganizationExtension.VIEW_COURSE, extension1.group, extension1)

        self.non_staff_user.groups.add(extension1.group)

        # Check Staff user get all groups
        response = self.client.get(self.list_path)

        self.assertEqual(response.status_code, 200)
        self.assert_response_data_valid(response, Organization.objects.all())

        # Check non staff user gets 1 group
        self.client.logout()
        self.client.login(username=self.non_staff_user.username, password=USER_PASSWORD)

        response = self.client.get(self.list_path)

        self.assertEqual(response.status_code, 200)
        self.assert_response_data_valid(response, [org1])

    def test_list_uuid_filter(self):
        """ Verify the endpoint returns a list of organizations filtered by UUID. """

        organizations = OrganizationFactory.create_batch(3, partner=self.partner)

        # Test with a single UUID
        self.assert_list_uuid_filter([organizations[0]], 7)

        # Test with multiple UUIDs
        self.assert_list_uuid_filter(organizations, 7)

    def test_list_tag_filter(self):
        """ Verify the endpoint returns a list of organizations filtered by tag. """

        tag = 'test-org'
        organizations = OrganizationFactory.create_batch(2, partner=self.partner)

        # If no organizations have been tagged, the endpoint should not return any data
        self.assert_list_tag_filter([], [tag], expected_query_count=5)

        # Tagged organizations should be returned
        organizations[0].tags.add(tag)
        self.assert_list_tag_filter([organizations[0]], [tag])

        # The endpoint should support filtering by multiple tags. The filter should be an OR filter, meaning the results
        # include any organization containing at least one of the given tags.
        tag2 = 'another-tag'
        organizations[1].tags.add(tag)
        self.assert_list_tag_filter(Organization.objects.all(), [tag, tag2])

    def test_retrieve(self):
        """ Verify the endpoint returns details for a single organization. """
        organization = OrganizationFactory(partner=self.partner)
        url = reverse('api:v1:organization-detail', kwargs={'uuid': organization.uuid})

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assert_response_data_valid(response, organization, many=False)

    def test_retrieve_not_staff(self):
        """ Verify the endpoint returns a list of all organizations. """
        org1 = OrganizationFactory.create(partner=self.partner)
        org2 = OrganizationFactory.create(partner=self.partner)
        OrganizationFactory.create(partner=self.partner)
        url = reverse('api:v1:organization-detail', kwargs={'uuid': org2.uuid})

        extension1 = publisher_factories.OrganizationExtensionFactory(organization=org1)
        publisher_factories.OrganizationExtensionFactory(organization=org2)

        assign_perm(OrganizationExtension.VIEW_COURSE, extension1.group, extension1)
        self.non_staff_user.groups.add(extension1.group)

        # Check Staff user get all groups
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assert_response_data_valid(response, org2, many=False)

        # Check non staff user gets 1 group
        self.client.logout()
        self.client.login(username=self.non_staff_user.username, password=USER_PASSWORD)

        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

        url = reverse('api:v1:organization-detail', kwargs={'uuid': org1.uuid})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assert_response_data_valid(response, org1, many=False)

    def test_retrieve_not_found(self):
        """ Verify the endpoint returns HTTP 404 if the specified UUID does not match an organization. """
        url = reverse('api:v1:organization-detail', kwargs={'uuid': uuid.uuid4()})

        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
