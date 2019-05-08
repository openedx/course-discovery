import uuid

from pytest import mark
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.journal.models import Journal
from course_discovery.apps.journal.tests.factories import JournalBundleFactory, JournalFactory


@mark.django_db
class JournalViewSetTests(APITestCase):
    """ Tests for the JournalViewSet. """

    def setUp(self):
        super(JournalViewSetTests, self).setUp()
        self.user = UserFactory(is_staff=True)
        self.journal = JournalFactory(uuid=uuid.uuid4())
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.journal_url = reverse('journal:api:v1:journal-list')

    def test_without_authentication(self):
        """ Verify authentication is required when accessing the endpoint. """
        self.client.logout()
        response = self.client.get(self.journal_url)
        self.assertEqual(response.status_code, 401)

    def test_create_journal(self):
        # create a second journal
        journal = JournalFactory()
        self.assertEqual(Journal.objects.count(), 2)

        data = {
            'uuid': str(uuid.uuid4()),
            'partner': journal.organization.partner.short_code,
            'organization': journal.organization.key,
            'title': 'API Created Journal',
            'price': '50.0',
            'currency': 'USD',
            'sku': 'ABC-111',
            'access_length': '365',
            'card_image_url': '',
            'short_description': 'A short desc',
            'full_description': 'A long desc',
            'status': 'active',
            'about_page_id': 66,
        }

        response = self.client.post(self.journal_url, data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Journal.objects.count(), 3)

    def test_list(self):
        """ Verify response on list view. """
        response = self.client.get(self.journal_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 1)
        self.assertTrue('partner' in response.data['results'][0])

    def test_list_with_organization_filter(self):
        """ Verify response on list view with organization filter"""

        # creating another journal
        journal = JournalFactory()

        self.assertEqual(Journal.objects.count(), 2)

        url_with_filter = '{url}?organization={org}'.format(url=self.journal_url, org=journal.organization.key)
        response = self.client.get(url_with_filter)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 1)

    def test_list_with_uuid_filter(self):
        """ Verify response on list view with uuid's filter"""

        journal_1 = JournalFactory()
        journal_2 = JournalFactory()
        self.assertEqual(Journal.objects.count(), 3)

        uuid_list = ','.join([str(journal_1.uuid), str(journal_2.uuid)])
        url_with_filter = '{url}?uuid={uuid}'.format(url=self.journal_url, uuid=uuid_list)
        response = self.client.get(url_with_filter)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 2)


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
        self.assertEqual(response.status_code, 401)

    def test_list(self):
        """ Verify response on list view. """
        response = self.client.get(self.journal_bundle_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 1)
        self.assertTrue('journals' in response.data['results'][0])
