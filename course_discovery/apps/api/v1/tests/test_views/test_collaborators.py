from rest_framework.reverse import reverse

from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase, OAuth2Mixin, SerializationMixin
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.tests.factories import CollaboratorFactory


class CollaboratorViewSetTests(OAuth2Mixin, SerializationMixin, APITestCase):
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
        url = reverse('api:v1:collaborator-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_add(self):
        self.mock_access_token()
        url = reverse('api:v1:collaborator-list')
        data = {'name': 'Collaborator 1'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 201)
        collab = response.json()
        self.assertEqual(collab['image_url'], None)

    def test_modify(self):
        self.mock_access_token()
        url = reverse('api:v1:collaborator-list')
        data = {'name': 'Collaborator 1'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 201)
        collab = response.json()
        patch_url = reverse('api:v1:collaborator-detail', kwargs={'uuid': collab['uuid']})
        collab['name'] = 'Collaborator 2'
        response2 = self.client.patch(patch_url, collab, format='json')
        modified_collab = response2.json()
        self.assertEqual(modified_collab['name'], 'Collaborator 2')
