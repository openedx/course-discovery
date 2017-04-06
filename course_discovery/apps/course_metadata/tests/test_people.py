import responses

from course_discovery.apps.core.tests.factories import PartnerFactory
from course_discovery.apps.course_metadata.exceptions import PersonToMarketingException
from course_discovery.apps.course_metadata.people import MarketingSitePeople
from course_discovery.apps.course_metadata.tests.mixins import MarketingSitePublisherTestMixin
from course_discovery.apps.course_metadata.utils import MarketingSiteAPIClient


class MarketingSitePublisherTests(MarketingSitePublisherTestMixin):
    """
    Unit test cases for the MarketingSitePeople
    """
    def setUp(self):
        super(MarketingSitePublisherTests, self).setUp()
        self.partner = PartnerFactory()
        self.partner.marketing_site_url_root = self.api_root
        self.partner.marketing_site_api_username = self.username
        self.partner.marketing_site_api_password = self.password

        self.api_client = MarketingSiteAPIClient(
            self.username,
            self.password,
            self.api_root
        )

        self.expected_node = {
            'resource': 'node', ''
            'id': '28691',
            'uuid': '18d5542f-fa80-418e-b416-455cfdeb4d4e',
            'uri': 'https://stage.edx.org/node/28691'
        }
        self.data = {
            'given_name': 'test',
            'family_name': 'user'
        }

    @responses.activate
    def test_create_node(self):
        self.mock_api_client(200)
        self.mock_node_create(self.expected_node, 201)
        people = MarketingSitePeople()
        data = people._create_node(self.api_client, self.data)  # pylint: disable=protected-access
        self.assertEqual(data, self.expected_node)

    @responses.activate
    def test_create_node_failed(self):
        self.mock_api_client(200)
        self.mock_node_create({}, 500)
        people = MarketingSitePeople()
        people_data = people._get_node_data(self.data)  # pylint: disable=protected-access
        with self.assertRaises(PersonToMarketingException):
            people._create_node(self.api_client, people_data)  # pylint: disable=protected-access

    @responses.activate
    def test_person_create(self):
        self.mock_api_client(200)
        self.mock_node_create(self.expected_node, 201)
        people = MarketingSitePeople()
        result = people.publish_person(self.partner, self.data)
        self.assertEqual(result, self.expected_node)

    @responses.activate
    def test_person_create_failed(self):
        self.mock_api_client(200)
        self.mock_node_create({}, 500)
        people = MarketingSitePeople()
        with self.assertRaises(PersonToMarketingException):
            people.publish_person(self.partner, self.data)

    @responses.activate
    def test_delete_program(self):
        self.mock_api_client(200)
        self.mock_node_delete(200)
        people = MarketingSitePeople()
        people.delete_person(self.partner, self.node_id)
