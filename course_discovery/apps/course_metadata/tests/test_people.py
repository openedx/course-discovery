import mock
import responses
from testfixtures import LogCapture

from course_discovery.apps.core.tests.factories import PartnerFactory
from course_discovery.apps.course_metadata.exceptions import PersonToMarketingException
from course_discovery.apps.course_metadata.people import MarketingSitePeople
from course_discovery.apps.course_metadata.tests.mixins import MarketingSitePublisherTestMixin
from course_discovery.apps.course_metadata.utils import MarketingSiteAPIClient

LOGGER_NAME = 'course_discovery.apps.course_metadata.people'


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
        self.uuid = '18d5542f-fa80-418e-b416-455cfdeb4d4e'

        self.expected_node = {
            'resource': 'node', ''
            'id': '28691',
            'uuid': self.uuid,
            'uri': 'https://stage.edx.org/node/28691'
        }
        self.data = {
            'given_name': 'test',
            'family_name': 'user'
        }
        self.updated_node_data = {
            'given_name': 'updated test',
            'family_name': 'user',
            'title': 'updated test user'
        }

    @responses.activate
    def test_create_node(self):
        self.mock_api_client(200)
        self.mock_node_create(self.expected_node, 201)
        people = MarketingSitePeople()
        data = people._create_node(self.api_client, self.data)  # pylint: disable=protected-access
        self.assertEqual(data, self.expected_node)

    @responses.activate
    def test_update_node(self):
        self.mock_api_client(200)
        self.mock_node_edit(200)
        people = MarketingSitePeople()
        data = people._update_node(self.api_client, self.node_id, self.updated_node_data)  # pylint: disable=protected-access
        self.assertEqual(data, {})

    @responses.activate
    def test_update_node_failed(self):
        self.mock_api_client(200)
        self.mock_node_edit(500)
        people = MarketingSitePeople()
        with self.assertRaises(PersonToMarketingException):
            people._update_node(self.api_client, self.node_id, self.data)  # pylint: disable=protected-access

    @responses.activate
    def test_update_person(self):
        self.mock_api_client(200)
        self.mock_node_edit(200)
        self.mock_node_retrieval('uuid', self.uuid, status=200)
        people = MarketingSitePeople()
        data = people.update_person(self.partner, self.uuid, self.updated_node_data)
        self.assertEqual(data, {})

    @responses.activate
    def test_update_person_failed(self):
        self.mock_api_client(200)
        self.mock_node_edit(500)
        self.mock_node_retrieval('uuid', self.uuid, status=200)
        people = MarketingSitePeople()
        with self.assertRaises(PersonToMarketingException):
            people.update_person(self.partner, self.uuid, self.updated_node_data)

    @responses.activate
    def test_get_node_id_from_uuid(self):
        self.mock_api_client(200)
        self.mock_node_retrieval('uuid', self.uuid, status=200)
        people = MarketingSitePeople()
        data = people._get_node_id_from_uuid(self.api_client, self.uuid)  # pylint: disable=protected-access
        self.assertEqual(data, self.node_id)

    @responses.activate
    def test_get_node_id_from_uuid_failed(self):
        self.mock_api_client(200)
        self.mock_node_retrieval('uuid', self.uuid, status=500)
        people = MarketingSitePeople()
        with self.assertRaises(PersonToMarketingException):
            people._get_node_id_from_uuid(self.api_client, self.uuid)  # pylint: disable=protected-access

    @mock.patch(
        'course_discovery.apps.course_metadata.people.MarketingSitePeople._get_node_id_from_uuid',
        mock.Mock(return_value=None)
    )
    def test_update_uuid_not_found(self):
        self.mock_api_client(200)
        people = MarketingSitePeople()
        with LogCapture(LOGGER_NAME) as log:
            people.update_person(self.partner, self.uuid, self.updated_node_data)
            log.check((LOGGER_NAME, 'INFO',
                       'Person with UUID [{}] does not exist on the marketing site'.format(self.uuid)))

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
    def test_delete_person(self):
        self.mock_api_client(200)
        self.mock_node_delete(200)
        people = MarketingSitePeople()
        people.delete_person(self.partner, self.node_id)

    @responses.activate
    def test_delete_person_by_uuid(self):
        self.mock_api_client(200)
        self.mock_node_retrieval('uuid', self.uuid, status=200)
        self.mock_node_delete(200)
        people = MarketingSitePeople()
        people.delete_person_by_uuid(self.partner, self.uuid)

    @mock.patch(
        'course_discovery.apps.course_metadata.people.MarketingSitePeople._get_node_id_from_uuid',
        mock.Mock(return_value=None)
    )
    def test_delete_person_by_uuid_not_found(self):
        people = MarketingSitePeople()
        with LogCapture(LOGGER_NAME) as log:
            people.delete_person_by_uuid(self.partner, self.uuid)
            log.check((LOGGER_NAME, 'INFO',
                       'Person with UUID [{}] does not exist on the marketing site'.format(self.uuid)))
