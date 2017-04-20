import mock
import responses

from django.utils.text import slugify

from course_discovery.apps.course_metadata.choices import ProgramStatus
from course_discovery.apps.course_metadata.models import ProgramType
from course_discovery.apps.course_metadata.publishers import (
    MarketingSiteAPIClient, MarketingSitePublisher, ProgramPublisherException
)
from course_discovery.apps.course_metadata.tests.factories import ProgramFactory
from course_discovery.apps.course_metadata.tests.mixins import MarketingSitePublisherTestMixin


class MarketingSitePublisherTests(MarketingSitePublisherTestMixin):
    """
    Unit test cases for the MarketingSitePublisher
    """
    def setUp(self):
        super(MarketingSitePublisherTests, self).setUp()
        self.program = ProgramFactory()
        self.slugified_title = slugify(self.program.title, allow_unicode=True)
        self.program.partner.marketing_site_url_root = self.api_root
        self.program.partner.marketing_site_api_username = self.username
        self.program.partner.marketing_site_api_password = self.password
        self.program.type = ProgramType.objects.get(name='MicroMasters')
        with mock.patch.object(MarketingSitePublisher, '_get_headers', return_value={}):
            with mock.patch.object(MarketingSitePublisher, '_get_form_build_id_and_form_token', return_value={}):
                self.program.save()  # pylint: disable=no-member
                self.api_client = MarketingSiteAPIClient(
                    self.username,
                    self.password,
                    self.api_root
                )
        self.expected_node = {
            'uuid': '945bb2c7-0a57-4a3f-972a-8c7f94aa0661',
            'resource': 'node',
            'uri': 'https://stage.edx.org/node/28426',
            'id': '28426'
        }

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
            'status': 1 if self.program.status == ProgramStatus.Active else 0
        }
        self.assertDictEqual(publish_data, expected)

    @responses.activate
    def test_get_node_id(self):
        self.mock_api_client(200)
        self.mock_node_retrieval(self.program.uuid)
        publisher = MarketingSitePublisher()
        node_id = publisher._get_node_id(self.api_client, self.program.uuid)  # pylint: disable=protected-access
        self.assert_responses_call_count(4)
        self.assertEqual(node_id, self.node_id)

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
        publisher._edit_node(self.api_client, self.node_id, publish_data)  # pylint: disable=protected-access
        self.assert_responses_call_count(4)

    @responses.activate
    def test_edit_node_failed(self):
        self.mock_api_client(200)
        self.mock_node_edit(500)
        publisher = MarketingSitePublisher()
        publish_data = publisher._get_node_data(self.program, self.user_id)  # pylint: disable=protected-access
        with self.assertRaises(ProgramPublisherException):
            publisher._edit_node(self.api_client, self.node_id, publish_data)  # pylint: disable=protected-access

    @responses.activate
    def test_create_node(self):
        self.mock_api_client(200)
        self.mock_node_create(self.expected_node, 201)
        publisher = MarketingSitePublisher()
        publish_data = publisher._get_node_data(self.program, self.user_id)  # pylint: disable=protected-access
        data = publisher._create_node(self.api_client, publish_data)  # pylint: disable=protected-access
        self.assertEqual(data, self.expected_node['id'])

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
        self.mock_node_retrieval(self.program.uuid, exists=False)
        self.mock_node_create(self.expected_node, 201)
        publisher = MarketingSitePublisher()
        self.mock_get_delete_form(self.slugified_title)
        self.mock_add_alias()
        with mock.patch.object(MarketingSitePublisher, '_get_headers', return_value={}):
            with mock.patch.object(MarketingSitePublisher, '_get_form_build_id_and_form_token', return_value={}):
                publisher.publish_program(self.program)
                self.assert_responses_call_count(9)

    @responses.activate
    def test_publish_program_edit(self):
        self.mock_api_client(200)
        self.mock_node_retrieval(self.program.uuid)
        self.mock_node_edit(200)
        publisher = MarketingSitePublisher()
        self.mock_get_delete_form(self.slugified_title)
        self.mock_add_alias()
        with mock.patch.object(MarketingSitePublisher, '_get_headers', return_value={}):
            with mock.patch.object(MarketingSitePublisher, '_get_form_build_id_and_form_token', return_value={}):
                publisher.publish_program(self.program)
                self.assert_responses_call_count(9)

    @responses.activate
    def test_publish_modified_program(self):
        self.mock_api_client(200)
        self.mock_node_retrieval(self.program.uuid)
        self.mock_node_edit(200)
        program_before = ProgramFactory()
        publisher = MarketingSitePublisher(program_before)
        self.mock_add_alias()
        self.mock_delete_alias()
        with mock.patch.object(MarketingSitePublisher, '_get_headers', return_value={}):
            with mock.patch.object(MarketingSitePublisher, '_get_form_build_id_and_form_token', return_value={}):
                with mock.patch.object(MarketingSitePublisher, '_get_delete_alias_url', return_value='/foo'):
                    publisher.publish_program(self.program)
                    self.assert_responses_call_count(9)

    @responses.activate
    def test_get_alias_form(self):
        self.mock_api_client(200)
        self.mock_node_retrieval(self.program.uuid)
        self.mock_node_edit(200)
        publisher = MarketingSitePublisher()
        self.mock_get_delete_form(self.slugified_title)
        self.mock_add_alias()
        self.mock_get_alias_form()
        with mock.patch.object(MarketingSitePublisher, '_get_headers', return_value={}):
            with mock.patch.object(MarketingSitePublisher, '_get_form_build_id_and_form_token', return_value={}):
                publisher.publish_program(self.program)
                self.assert_responses_call_count(9)

    @responses.activate
    def test_get_delete_form(self):
        self.mock_api_client(200)
        self.mock_node_retrieval(self.program.uuid)
        self.mock_node_edit(200)
        program_before = ProgramFactory()
        publisher = MarketingSitePublisher(program_before)
        self.mock_get_delete_form(self.slugified_title)
        self.mock_add_alias()
        self.mock_get_delete_form(program_before.marketing_slug)
        with mock.patch.object(MarketingSitePublisher, '_get_headers', return_value={}):
            with mock.patch.object(MarketingSitePublisher, '_get_form_build_id_and_form_token', return_value={}):
                publisher.publish_program(self.program)
                self.assert_responses_call_count(11)

    @responses.activate
    def test_get_alias_form_failed(self):
        self.mock_api_client(200)
        self.mock_node_retrieval(self.program.uuid)
        self.mock_node_edit(200)
        publisher = MarketingSitePublisher()
        self.mock_get_delete_form(self.slugified_title)
        self.mock_add_alias()
        self.mock_get_alias_form(500)
        with mock.patch.object(MarketingSitePublisher, '_get_headers', return_value={}):
            with mock.patch.object(MarketingSitePublisher, '_delete_title_alias', return_value={}):
                with self.assertRaises(ProgramPublisherException):
                    publisher.publish_program(self.program)

    @responses.activate
    def test_delete_title_alias_failed(self):
        self.mock_api_client(200)
        self.mock_node_retrieval(self.program.uuid)
        self.mock_node_edit(200)
        publisher = MarketingSitePublisher()
        self.mock_get_delete_form(self.slugified_title)
        with mock.patch.object(MarketingSitePublisher, '_get_headers', return_value={}):
            with self.assertRaises(ProgramPublisherException):
                publisher.publish_program(self.program)

    @responses.activate
    def test_get_delete_form_failed(self):
        self.mock_api_client(200)
        self.mock_node_retrieval(self.program.uuid)
        self.mock_node_edit(200)
        program_before = ProgramFactory()
        publisher = MarketingSitePublisher(program_before)
        self.mock_get_delete_form(self.slugified_title)
        self.mock_add_alias()
        self.mock_get_delete_form(program_before.marketing_slug, 500)
        with mock.patch.object(MarketingSitePublisher, '_get_headers', return_value={}):
            with mock.patch.object(MarketingSitePublisher, '_get_form_build_id_and_form_token', return_value={}):
                with self.assertRaises(ProgramPublisherException):
                    publisher.publish_program(self.program)

    @responses.activate
    def test_add_alias_failed(self):
        self.mock_api_client(200)
        self.mock_node_retrieval(self.program.uuid)
        self.mock_node_edit(200)
        publisher = MarketingSitePublisher()
        self.mock_get_delete_form(self.slugified_title)
        self.mock_add_alias(500)
        with mock.patch.object(MarketingSitePublisher, '_get_form_build_id_and_form_token', return_value={}):
            with self.assertRaises(ProgramPublisherException):
                publisher.publish_program(self.program)

    @responses.activate
    def test_publish_unmodified_program(self):
        self.mock_api_client(200)
        publisher = MarketingSitePublisher(self.program)
        publisher.publish_program(self.program)
        self.assert_responses_call_count(0)

    @responses.activate
    def test_publish_xseries_program(self):
        self.program.type = ProgramType.objects.get(name='XSeries')
        publisher = MarketingSitePublisher()
        publisher.publish_program(self.program)
        self.assert_responses_call_count(0)

    @responses.activate
    def test_publish_program_no_credential(self):
        self.program.partner.marketing_site_api_password = None
        self.program.partner.marketing_site_api_username = None
        publisher = MarketingSitePublisher()
        with self.assertRaises(ProgramPublisherException):
            publisher.publish_program(self.program)
            self.assert_responses_call_count(0)

    @responses.activate
    def test_publish_delete_program(self):
        self.mock_api_client(200)
        self.mock_node_retrieval(self.program.uuid)
        self.mock_node_delete(204)
        publisher = MarketingSitePublisher()
        publisher.delete_program(self.program)
        self.assert_responses_call_count(5)

    @responses.activate
    def test_publish_delete_non_existent_program(self):
        self.mock_api_client(200)
        self.mock_node_retrieval(self.program.uuid, exists=False)
        publisher = MarketingSitePublisher()
        publisher.delete_program(self.program)
        self.assert_responses_call_count(4)

    @responses.activate
    def test_publish_delete_xseries(self):
        self.program = ProgramFactory(type=ProgramType.objects.get(name='XSeries'))
        publisher = MarketingSitePublisher()
        publisher.delete_program(self.program)
        self.assert_responses_call_count(0)
