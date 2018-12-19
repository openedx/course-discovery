import ddt
import mock
import responses
from testfixtures import LogCapture

from course_discovery.apps.core.tests.factories import PartnerFactory
from course_discovery.apps.course_metadata.exceptions import PersonToMarketingException
from course_discovery.apps.course_metadata.people import MarketingSitePeople
from course_discovery.apps.course_metadata.tests.factories import PersonFactory
from course_discovery.apps.course_metadata.tests.mixins import MarketingSitePublisherTestMixin
from course_discovery.apps.course_metadata.utils import MarketingSiteAPIClient

LOGGER_NAME = 'course_discovery.apps.course_metadata.people'


@ddt.ddt
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
        self.person = PersonFactory(partner=self.partner, given_name='Test', family_name='User')

        self.api_client = MarketingSiteAPIClient(
            self.username,
            self.password,
            self.api_root
        )
        self.uuid = str(self.person.uuid)

        self.expected_node = {
            'resource': 'node',
            'id': '28691',
            'uuid': self.uuid,
            'uri': 'https://stage.edx.org/node/28691'
        }
        self.expected_data = {
            'type': 'person',
            'title': 'Test User',
            'field_person_slug': 'test-user',
            'status': 1
        }

    @responses.activate
    def test_create_node(self):
        self.mock_api_client(200)
        self.mock_node_create(self.expected_node, 201)
        people = MarketingSitePeople()
        data = people._create_node(self.api_client, {})  # pylint: disable=protected-access
        self.assertEqual(data, self.expected_node)

    @responses.activate
    def test_update_node(self):
        self.mock_api_client(200)
        self.mock_node_edit(200)
        people = MarketingSitePeople()
        data = people._update_node(self.api_client, self.node_id, {})  # pylint: disable=protected-access
        self.assertEqual(data, {})

    @responses.activate
    def test_update_node_failed(self):
        self.mock_api_client(200)
        self.mock_node_edit(500)
        people = MarketingSitePeople()
        with self.assertRaises(PersonToMarketingException):
            people._update_node(self.api_client, self.node_id, {})  # pylint: disable=protected-access

    @responses.activate
    @ddt.data(True, False)
    def test_update_or_publish_person(self, exists):
        self.mock_api_client(200)
        if exists:
            self.mock_node_edit(200)
        else:
            self.mock_node_create(self.expected_node, 201)
        self.mock_node_retrieval('uuid', self.uuid, exists=exists, status=200)
        people = MarketingSitePeople()
        result = people.update_or_publish_person(self.person)
        if exists:
            self.assertEqual(result, {})
        else:
            self.assertEqual(result, self.expected_node)

    @responses.activate
    @mock.patch('course_discovery.apps.course_metadata.people.MarketingSitePeople._update_node')
    def test_update_person_json(self, mock_update_node):
        self.mock_api_client(200)
        self.mock_node_retrieval('uuid', self.uuid, status=200)
        people = MarketingSitePeople()
        people.update_or_publish_person(self.person)
        self.assertEqual(mock_update_node.call_count, 1)
        data = mock_update_node.call_args[0][2]
        self.assertDictEqual(data, self.expected_data)

    @responses.activate
    def test_update_person_failed(self):
        self.mock_api_client(200)
        self.mock_node_edit(500)
        self.mock_node_retrieval('uuid', self.uuid, status=200)
        people = MarketingSitePeople()
        with self.assertRaises(PersonToMarketingException):
            people.update_or_publish_person(self.person)

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

    @responses.activate
    def test_create_node_failed(self):
        self.mock_api_client(200)
        self.mock_node_create({}, 500)
        people = MarketingSitePeople()
        people_data = people._get_node_data(self.person)  # pylint: disable=protected-access
        with self.assertRaises(PersonToMarketingException):
            people._create_node(self.api_client, people_data)  # pylint: disable=protected-access

    @mock.patch('course_discovery.apps.course_metadata.people.MarketingSitePeople._create_node')
    def test_person_create_json(self, mock_create_node):
        self.mock_api_client(200)
        self.mock_node_retrieval('uuid', self.uuid, exists=False, status=200)
        people = MarketingSitePeople()
        people.update_or_publish_person(self.person)
        self.assertEqual(mock_create_node.call_count, 1)
        data = mock_create_node.call_args[0][1]
        expected = self.expected_data
        expected.update({
            'status': 1,
            'uuid': self.uuid,
        })
        self.assertDictEqual(data, expected)

    @responses.activate
    def test_person_create_failed(self):
        self.mock_api_client(200)
        self.mock_node_create({}, 500)
        self.mock_node_retrieval('uuid', self.uuid, exists=False, status=200)
        people = MarketingSitePeople()
        with self.assertRaises(PersonToMarketingException):
            people.update_or_publish_person(self.person)

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
