from django.urls import reverse

from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase, SerializationMixin
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.models import Source
from course_discovery.apps.course_metadata.tests.factories import SourceFactory


class SourceViewSetTests(SerializationMixin, APITestCase):
    list_path = reverse('api:v1:source-list')

    def setUp(self):
        super().setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.non_staff_user = UserFactory()
        self.request.user = self.user
        self.client.login(username=self.user.username, password=USER_PASSWORD)

    def test_authentication(self):
        """ Verify the endpoint requires the user to be authenticated. """
        response = self.client.get(self.list_path)
        assert response.status_code == 200

        self.client.logout()
        response = self.client.get(self.list_path)
        assert response.status_code == 401

    def assert_response_data_valid(self, response, source, many=True):
        """ Asserts the response data (only) contains the expected sources. """
        actual = response.data
        serializer_data = self.serialize_source(source, many=many)
        if many:
            actual = actual['results']

        self.assertCountEqual(actual, serializer_data)

    def test_list(self):
        """ Verify the endpoint returns a list of all sources. """
        SourceFactory.create_batch(3)

        with self.assertNumQueries(4):
            response = self.client.get(self.list_path)

        assert response.status_code == 200
        self.assert_response_data_valid(response, Source.objects.all())

    def test_retrieve(self):
        """ Verify the endpoint returns details for a single source. """
        source = SourceFactory()
        url = reverse('api:v1:source-detail', kwargs={'slug': source.slug})
        response = self.client.get(url)
        assert response.status_code == 200
        self.assert_response_data_valid(response, source, many=False)

    def test_retrieve_not_found(self):
        """ Verify the endpoint returns HTTP 404 if the specified slug does not match an source."""
        url = reverse('api:v1:source-detail', kwargs={'slug': 'test-string'})
        response = self.client.get(url)
        assert response.status_code == 404
