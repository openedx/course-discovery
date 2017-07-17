import uuid

from django.urls import reverse
from rest_framework.test import APITestCase

from course_discovery.apps.api.v1.tests.test_views.mixins import SerializationMixin
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.tests.factories import Organization, OrganizationFactory


class OrganizationViewSetTests(SerializationMixin, APITestCase):
    list_path = reverse('api:v1:organization-list')

    def setUp(self):
        super(OrganizationViewSetTests, self).setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.client.login(username=self.user.username, password=USER_PASSWORD)

    def test_authentication(self):
        """ Verify the endpoint requires the user to be authenticated. """
        response = self.client.get(self.list_path)
        self.assertEqual(response.status_code, 200)

        self.client.logout()
        response = self.client.get(self.list_path)
        self.assertEqual(response.status_code, 403)

    def assert_response_data_valid(self, response, organizations, many=True):
        """ Asserts the response data (only) contains the expected organizations. """

        actual = response.data
        if many:
            actual = actual['results']

        self.assertEqual(actual, self.serialize_organization(organizations, many=many))

    def assert_list_uuid_filter(self, organizations):
        """ Asserts the list endpoint supports filtering by UUID. """

        with self.assertNumQueries(5):
            uuids = ','.join([organization.uuid.hex for organization in organizations])
            url = '{root}?uuids={uuids}'.format(root=self.list_path, uuids=uuids)
            response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assert_response_data_valid(response, organizations)

    def assert_list_tag_filter(self, organizations, tags, expected_query_count=5):
        """ Asserts the list endpoint supports filtering by tags. """

        with self.assertNumQueries(expected_query_count):
            tags = ','.join(tags)
            url = '{root}?tags={tags}'.format(root=self.list_path, tags=tags)
            response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assert_response_data_valid(response, organizations)

    def test_list(self):
        """ Verify the endpoint returns a list of all organizations. """

        OrganizationFactory.create_batch(3)

        with self.assertNumQueries(5):
            response = self.client.get(self.list_path)

        self.assertEqual(response.status_code, 200)
        self.assert_response_data_valid(response, Organization.objects.all())

    def test_list_uuid_filter(self):
        """ Verify the endpoint returns a list of organizations filtered by UUID. """

        organizations = OrganizationFactory.create_batch(3)

        # Test with a single UUID
        self.assert_list_uuid_filter([organizations[0]])

        # Test with multiple UUIDs
        self.assert_list_uuid_filter(organizations)

    def test_list_tag_filter(self):
        """ Verify the endpoint returns a list of organizations filtered by tag. """

        tag = 'test-org'
        organizations = OrganizationFactory.create_batch(2)

        # If no organizations have been tagged, the endpoint should not return any data
        self.assert_list_tag_filter([], [tag], expected_query_count=3)

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
        organization = OrganizationFactory()
        url = reverse('api:v1:organization-detail', kwargs={'uuid': organization.uuid})

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assert_response_data_valid(response, organization, many=False)

    def test_retrieve_not_found(self):
        """ Verify the endpoint returns HTTP 404 if the specified UUID does not match an organization. """
        url = reverse('api:v1:organization-detail', kwargs={'uuid': uuid.uuid4()})

        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
