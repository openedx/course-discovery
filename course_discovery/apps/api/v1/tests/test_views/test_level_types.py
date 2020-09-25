from django.urls import reverse

from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase, SerializationMixin
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.models import LevelType
from course_discovery.apps.course_metadata.tests.factories import LevelTypeFactory


class LevelTypeViewSetTests(SerializationMixin, APITestCase):
    list_path = reverse('api:v1:level_type-list')

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
        """ Verify the endpoint returns a list of all program types. """
        LevelTypeFactory.create_batch(4)
        expected = LevelType.objects.all()
        with self.assertNumQueries(6):
            response = self.client.get(self.list_path)

        assert response.status_code == 200
        assert response.data['results'] == self.serialize_level_type(expected, many=True)

    def test_retrieve(self):
        """ The request should return details for a single level type. """
        level_type = LevelTypeFactory()
        level_type.set_current_language('en')
        level_type.name_t = level_type.name
        level_type.save()
        url = reverse('api:v1:level_type-detail', kwargs={'name': level_type.name})
        print(level_type.__dict__)

        with self.assertNumQueries(5):
            response = self.client.get(url)

        assert response.status_code == 200
        assert response.data == self.serialize_level_type(level_type)
