from django.urls import reverse

from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase, SerializationMixin
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.tests.factories import SubjectFactory


class SubjectViewSetTests(SerializationMixin, APITestCase):
    list_path = reverse('api:v1:subject-list')

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

    def test_retrieve(self):
        """ The request should return details for a single subject. """
        subject = SubjectFactory()
        url = reverse('api:v1:subject-detail', kwargs={'uuid': subject.uuid})

        with self.assertNumQueries(4):
            response = self.client.get(url)

        assert response.status_code == 200
        assert response.data == self.serialize_subject(subject)
