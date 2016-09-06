from django.test import TestCase
import responses

from course_discovery.apps.course_metadata.publishers import (
    MarketingSiteAPIClient,
    MarketingSitePublisher,
    ProgramPublisherException,
)
from course_discovery.apps.course_metadata.tests.factories import ProgramFactory
from course_discovery.apps.course_metadata.tests.mixins import (
    MarketingSiteAPIClientTestMixin,
    MarketingSitePublisherTestMixin,
)
from course_discovery.apps.course_metadata.models import Program


class MarketingSiteAPIClientTests(MarketingSiteAPIClientTestMixin, TestCase):
    """
    Unit test cases for MarketinSiteAPIClient
    """
    def setUp(self):
        super(MarketingSiteAPIClientTests, self).setUp()
        self.api_client = MarketingSiteAPIClient(
            self.username,
            self.password,
            self.api_root
        )

    @responses.activate
    def test_init_session(self):
        self.mock_login_response(200)
        session = self.api_client.init_session
        self.assertEqual(len(responses.calls), 2)
        self.assertIsNotNone(session)

    @responses.activate
    def test_init_session_failed(self):
        self.mock_login_response(500)
        with self.assertRaises(ProgramPublisherException):
            self.api_client.init_session  # pylint: disable=pointless-statement

    @responses.activate
    def test_csrf_token(self):
        self.mock_login_response(200)
        self.mock_csrf_token_response(200)
        csrf_token = self.api_client.csrf_token
        self.assertEqual(len(responses.calls), 3)
        self.assertEqual(self.csrf_token, csrf_token)

    @responses.activate
    def test_csrf_token_failed(self):
        self.mock_login_response(200)
        self.mock_csrf_token_response(500)
        with self.assertRaises(ProgramPublisherException):
            self.api_client.csrf_token  # pylint: disable=pointless-statement

    @responses.activate
    def test_user_id(self):
        self.mock_login_response(200)
        self.mock_user_id_response(200)
        user_id = self.api_client.user_id
        self.assertEqual(len(responses.calls), 3)
        self.assertEqual(self.user_id, user_id)

    @responses.activate
    def test_user_id_failed(self):
        self.mock_login_response(200)
        self.mock_user_id_response(500)
        with self.assertRaises(ProgramPublisherException):
            self.api_client.user_id  # pylint: disable=pointless-statement

    @responses.activate
    def test_api_session(self):
        self.mock_login_response(200)
        self.mock_csrf_token_response(200)
        api_session = self.api_client.api_session
        self.assertEqual(len(responses.calls), 3)
        self.assertIsNotNone(api_session)
        self.assertEqual(api_session.headers.get('Content-Type'), 'application/json')
        self.assertEqual(api_session.headers.get('X-CSRF-Token'), self.csrf_token)

    @responses.activate
    def test_api_session_failed(self):
        self.mock_login_response(500)
        self.mock_csrf_token_response(500)
        with self.assertRaises(ProgramPublisherException):
            self.api_client.api_session  # pylint: disable=pointless-statement


class MarketingSitePublisherTests(MarketingSitePublisherTestMixin, TestCase):
    """
    Unit test cases for the MarketingSitePublisher
    """
    def setUp(self):
        super(MarketingSitePublisherTests, self).setUp()
        self.program = ProgramFactory()
        self.program.partner.marketing_site_url_root = self.api_root
        self.program.partner.marketing_site_api_username = self.username
        self.program.partner.marketing_site_api_password = self.password
        self.program.save()  # pylint: disable=no-member
        self.api_client = MarketingSiteAPIClient(
            self.username,
            self.password,
            self.api_root
        )

    def test_get_node_data(self):
        publisher = MarketingSitePublisher()
        publish_data = publisher._get_node_data(self.program, self.user_id)  # pylint: disable=protected-access
        expected = {
            'type': str(self.program.type).lower(),
            'title': self.program.title,
            'field_uuid': str(self.program.uuid),
            'uuid': str(self.program.uuid),
            'author': {
                'id': self.user_id,
            },
            'status': 1 if self.program.status == Program.Status.Active else 0
        }
        self.assertDictEqual(publish_data, expected)

    @responses.activate
    def test_get_node_id(self):
        self.mock_api_client(200)
        self.mock_node_retrieval(self.program.uuid)
        publisher = MarketingSitePublisher()
        node_id = publisher._get_node_id(self.api_client, self.program.uuid)  # pylint: disable=protected-access
        self.assertEqual(len(responses.calls), 4)
        self.assertEqual(node_id, self.nid)

    @responses.activate
    def test_get_non_existent_node_id(self):
        self.mock_api_client(200)
        self.mock_node_retrieval(self.program.uuid, exists=False)
        publisher = MarketingSitePublisher()
        node_id = publisher._get_node_id(self.api_client, self.program.uuid)  # pylint: disable=protected-access
        self.assertIsNone(node_id)

    @responses.activate
    def test_edit_node(self):
        self.mock_api_client(200)
        self.mock_node_edit(200)
        publisher = MarketingSitePublisher()
        publish_data = publisher._get_node_data(self.program, self.user_id)  # pylint: disable=protected-access
        publisher._edit_node(self.api_client, self.nid, publish_data)  # pylint: disable=protected-access
        self.assertEqual(len(responses.calls), 4)

    @responses.activate
    def test_edit_node_failed(self):
        self.mock_api_client(200)
        self.mock_node_edit(500)
        publisher = MarketingSitePublisher()
        publish_data = publisher._get_node_data(self.program, self.user_id)  # pylint: disable=protected-access
        with self.assertRaises(ProgramPublisherException):
            publisher._edit_node(self.api_client, self.nid, publish_data)  # pylint: disable=protected-access

    @responses.activate
    def test_create_node(self):
        self.mock_api_client(200)
        expected = {
            'list': [{
                'nid': self.nid
            }]
        }
        self.mock_node_create(expected, 201)
        publisher = MarketingSitePublisher()
        publish_data = publisher._get_node_data(self.program, self.user_id)  # pylint: disable=protected-access
        data = publisher._create_node(self.api_client, publish_data)  # pylint: disable=protected-access
        self.assertEqual(data, expected)

    @responses.activate
    def test_create_node_failed(self):
        self.mock_api_client(200)
        self.mock_node_create({}, 500)
        publisher = MarketingSitePublisher()
        publish_data = publisher._get_node_data(self.program, self.user_id)  # pylint: disable=protected-access
        with self.assertRaises(ProgramPublisherException):
            publisher._create_node(self.api_client, publish_data)  # pylint: disable=protected-access

    @responses.activate
    def test_publish_program_create(self):
        self.mock_api_client(200)
        expected = {
            'list': [{
                'nid': self.nid
            }]
        }
        self.mock_node_retrieval(self.program.uuid, exists=False)
        self.mock_node_create(expected, 201)
        publisher = MarketingSitePublisher()
        publisher.publish_program(self.program)
        self.assertEqual(len(responses.calls), 6)

    @responses.activate
    def test_publish_program_edit(self):
        self.mock_api_client(200)
        self.mock_node_retrieval(self.program.uuid)
        self.mock_node_edit(200)
        publisher = MarketingSitePublisher()
        publisher.publish_program(self.program)
        self.assertEqual(len(responses.calls), 6)

    @responses.activate
    def test_publish_modified_program(self):
        self.mock_api_client(200)
        self.mock_node_retrieval(self.program.uuid)
        self.mock_node_edit(200)
        program_before = ProgramFactory()
        publisher = MarketingSitePublisher(program_before)
        publisher.publish_program(self.program)
        self.assertEqual(len(responses.calls), 6)

    @responses.activate
    def test_publish_unmodified_program(self):
        self.mock_api_client(200)
        publisher = MarketingSitePublisher(self.program)
        publisher.publish_program(self.program)
        self.assertEqual(len(responses.calls), 0)
