from rest_framework.reverse import reverse

from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase, SerializationMixin
from course_discovery.apps.core.tests.factories import USER_PASSWORD
from course_discovery.apps.course_metadata.tests.factories import CollaboratorFactory, UserFactory


class CollaboratorViewSetTests(SerializationMixin, APITestCase):
    """ Tests for the collaborator resource. """

    def setUp(self):
        super(CollaboratorViewSetTests, self).setUp()
        self.user = UserFactory(is_staff=True)
        self.request.user = self.user
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.name = 'Test User 1'
        self.collaborator = CollaboratorFactory(name=self.name)

    def tearDown(self):
        super(CollaboratorViewSetTests, self).tearDown()
        self.client.logout()

    def test_get(self):
        url = reverse('api:v1:collaborators', kwargs={'name': self.name})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)
