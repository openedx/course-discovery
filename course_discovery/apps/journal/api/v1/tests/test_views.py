from pytest import mark
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.journal.tests.factories import JournalBundleFactory, JournalFactory


@mark.django_db
class JournalViewSetTests(APITestCase):
    """ Tests for the JournalViewSet. """

    def setUp(self):
        super(JournalViewSetTests, self).setUp()
        self.user = UserFactory(is_staff=True)
        self.journal = JournalFactory()
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.journal_url = reverse('journal:api:v1:journal-list')

    def test_without_authentication(self):
        """ Verify authentication is required when accessing the endpoint. """
        self.client.logout()
        response = self.client.get(self.journal_url)
        self.assertEqual(response.status_code, 403)

    def test_list(self):
        """ Verify response on list view. """
        response = self.client.get(self.journal_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 1)
        self.assertTrue('partner' in response.data['results'][0])


@mark.django_db
class JournalBundleViewSetTests(APITestCase):
    """ Tests for the JournalBundleViewSet. """

    def setUp(self):
        super(JournalBundleViewSetTests, self).setUp()
        self.user = UserFactory(is_staff=True)
        self.journal_bundle = JournalBundleFactory()
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.journal_bundle_url = reverse('journal:api:v1:journal_bundle-list')

    def test_without_authentication(self):
        """ Verify authentication is required when accessing the endpoint. """
        self.client.logout()
        response = self.client.get(self.journal_bundle_url)
        self.assertEqual(response.status_code, 403)

    def test_list(self):
        """ Verify response on list view. """
        response = self.client.get(self.journal_bundle_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 1)
        self.assertTrue('journals' in response.data['results'][0])
