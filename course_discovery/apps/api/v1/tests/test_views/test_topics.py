from django.urls import reverse

from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase, SerializationMixin
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.models import Topic
from course_discovery.apps.course_metadata.tests.factories import TopicFactory


class TopicViewSetTests(SerializationMixin, APITestCase):
    list_path = reverse('api:v1:topic-list')

    def setUp(self):
        super().setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.client.login(username=self.user.username, password=USER_PASSWORD)

    def test_authentication(self):
        """ Verify the endpoint requires the user to be authenticated. """
        response = self.client.get(self.list_path)
        assert response.status_code == 200

        self.client.logout()
        response = self.client.get(self.list_path)
        assert response.status_code == 401

    def test_list(self):
        """ Verify the endpoint returns a list of all topic. """
        TopicFactory.create_batch(8)
        expected = Topic.objects.all()
        response = self.client.get(self.list_path)

        assert response.status_code == 200
        assert response.data['results'] == self.serialize_topic(expected, many=True)

    def test_retrieve(self):
        """ The request should return details for a single topic. """
        topic = TopicFactory()
        url = reverse('api:v1:topic-detail', kwargs={'uuid': topic.uuid})

        response = self.client.get(url)

        assert response.status_code == 200
        assert response.data == self.serialize_topic(topic)
