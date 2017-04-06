import json
import urllib

import responses
from django.test import TestCase
from factory.fuzzy import FuzzyInteger, FuzzyText

from course_discovery.apps.core.tests.utils import FuzzyUrlRoot


class MarketingSiteAPIClientTestMixin(TestCase):
    """
    The mixing to help mock the responses for marketing site API Client
    """
    def setUp(self):
        super(MarketingSiteAPIClientTestMixin, self).setUp()
        self.username = FuzzyText().fuzz()
        self.password = FuzzyText().fuzz()
        self.api_root = FuzzyUrlRoot().fuzz()
        self.csrf_token = FuzzyText().fuzz()
        self.user_id = FuzzyInteger(1).fuzz()

    def mock_login_response(self, status):
        """ Mock the response of the marketing site login """
        response_url = '{root}/admin'.format(
            root=self.api_root
        )

        def request_callback(request):  # pylint: disable=unused-argument
            headers = {
                'location': response_url
            }
            return (302, headers, None)

        responses.add_callback(
            responses.POST,
            '{root}/user'.format(root=self.api_root),
            callback=request_callback,
            content_type='text/html',
        )

        responses.add(
            responses.GET,
            response_url,
            body='',
            content_type='text/html',
            status=status
        )

    def mock_csrf_token_response(self, status):
        responses.add(
            responses.GET,
            '{root}/restws/session/token'.format(root=self.api_root),
            body=self.csrf_token,
            content_type='text/html',
            status=status
        )

    def mock_user_id_response(self, status):
        data = {
            'list': [{
                'uid': self.user_id
            }]
        }
        responses.add(
            responses.GET,
            '{root}/user.json?name={username}'.format(root=self.api_root, username=self.username),
            body=json.dumps(data),
            content_type='application/json',
            status=status,
            match_querystring=True
        )

    def assert_responses_call_count(self, count):
        self.assertEqual(len(responses.calls), count)


class MarketingSitePublisherTestMixin(MarketingSiteAPIClientTestMixin):
    """
    The mixing to help mock the responses for marketing site publisher
    """
    def setUp(self):
        super(MarketingSitePublisherTestMixin, self).setUp()
        self.node_id = FuzzyText().fuzz()

    def mock_api_client(self, status):
        self.mock_login_response(status)
        self.mock_csrf_token_response(status)
        self.mock_user_id_response(status)

    def mock_node_retrieval(self, program_uuid, exists=True):
        data = {}
        status = 200
        data = {
            'list': []
        }
        if exists:
            data['list'] = [{
                'nid': self.node_id
            }]

        responses.add(
            responses.GET,
            '{root}/node.json?field_uuid={uuid}'.format(root=self.api_root, uuid=str(program_uuid)),
            body=json.dumps(data),
            content_type='application/json',
            status=status,
            match_querystring=True
        )

    def mock_add_alias(self, status=200):
        node_url = 'node/{node_id}'.format(node_id=self.node_id)
        alias = '{program_type}/{slug}'.format(
            program_type=self.program.type.name.lower(),
            slug=self.program.marketing_slug
        )
        data = {
            'source': node_url,
            'alias': alias,
            'form_id': 'path_admin_form',
            'op': 'Save'
        }
        responses.add(
            responses.POST,
            '{root}/admin/config/search/path/add'.format(root=self.api_root),
            body=urllib.parse.urlencode(data),
            status=status
        )

    def mock_delete_alias(self, status=200):
        data = {
            "confirm": 1,
            "form_id": "path_admin_delete_confirm",
            "op": "Confirm"
        }
        responses.add(
            responses.POST,
            '{root}/foo'.format(root=self.api_root),
            body=urllib.parse.urlencode(data),
            status=status
        )

    def mock_get_alias_form(self, status=200):
        responses.add(
            responses.GET,
            '{root}/admin/config/search/path/add'.format(root=self.api_root),
            status=status,
            body='<html><form><input name="form_build_id" value="1">'
                 '</input><input name="form_token" value="2"></input></form></html>'
        )

    def mock_get_delete_form(self, alias, status=200):
        responses.add(
            responses.GET,
            '{root}/admin/config/search/path/list/{alias}'.format(root=self.api_root, alias=alias),
            status=status,
            body='<li class="delete last"><a href="/admin/config/search/path/delete/bar"></a></li>'
        )

        responses.add(
            responses.POST,
            '{root}/admin/config/search/path/delete/bar'.format(root=self.api_root),
            status=status
        )

    def mock_node_edit(self, status):
        responses.add(
            responses.PUT,
            '{root}/node.json/{node_id}'.format(root=self.api_root, node_id=self.node_id),
            body=json.dumps({}),
            content_type='application/json',
            status=status
        )

    def mock_node_create(self, response_data, status):
        responses.add(
            responses.POST,
            '{root}/node.json'.format(root=self.api_root),
            body=json.dumps(response_data),
            content_type='application/json',
            status=status
        )

    def mock_node_delete(self, status):
        responses.add(
            responses.DELETE,
            '{root}/node.json/{node_id}'.format(root=self.api_root, node_id=self.node_id),
            body='',
            content_type='text/html',
            status=status
        )
