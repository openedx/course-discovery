import json
import requests

from django.utils.functional import cached_property


class ProgramPublisherException(Exception):
    def __init__(self, message):
        super(ProgramPublisherException, self).__init__(message)
        suffix = 'The program data has not been saved. Please check your marketing site configuration'
        self.message = '{exception_msg} {suffix}'.format(exception_msg=message, suffix=suffix)


class MarketingSiteAPIClient(object):
    """
    The marketing site API client we can use to communicate with the marketing site
    """
    username = None
    password = None
    api_url = None

    def __init__(self, marketing_site_api_username, marketing_site_api_password, api_url):
        if not (marketing_site_api_username and marketing_site_api_password):
            raise ProgramPublisherException('Marketing Site API credentials are not properly configured!')
        self.username = marketing_site_api_username
        self.password = marketing_site_api_password
        self.api_url = api_url.strip('/')

    @cached_property
    def init_session(self):
        # Login to set session cookies
        session = requests.Session()
        login_url = '{root}/user'.format(root=self.api_url)
        login_data = {
            'name': self.username,
            'pass': self.password,
            'form_id': 'user_login',
            'op': 'Log in',
        }
        response = session.post(login_url, data=login_data)
        expected_url = '{root}/users/{username}'.format(root=self.api_url, username=self.username)
        if not (response.status_code == 200 and response.url == expected_url):
            raise ProgramPublisherException('Marketing Site Login failed!')
        return session

    @cached_property
    def api_session(self):
        self.init_session.headers.update(self.headers)
        return self.init_session

    @cached_property
    def csrf_token(self):
        token_url = '{root}/restws/session/token'.format(root=self.api_url)
        response = self.init_session.get(token_url)
        if not response.status_code == 200:
            raise ProgramPublisherException('Failed to retrieve Marketing Site CSRF token!')
        token = response.content.decode('utf8')
        return token

    @cached_property
    def user_id(self):
        # Get a user ID
        user_url = '{root}/user.json?name={username}'.format(root=self.api_url, username=self.username)
        response = self.init_session.get(user_url)
        if not response.status_code == 200:
            raise ProgramPublisherException('Failed to retrieve Marketing site user details!')
        user_id = response.json()['list'][0]['uid']
        return user_id

    @cached_property
    def headers(self):
        return {
            'Content-Type': 'application/json',
            'X-CSRF-Token': self.csrf_token,
        }


class MarketingSitePublisher(object):
    """
    This is the publisher that would publish the object data to marketing site
    """
    data_before = None

    def __init__(self, program_before=None):
        if program_before:
            self.data_before = {
                'type': program_before.type,
                'status': program_before.status,
                'title': program_before.title,
            }

    def _get_node_data(self, program, user_id):
        return {
            'type': str(program.type).lower(),
            'title': program.title,
            'field_uuid': str(program.uuid),
            'uuid': str(program.uuid),
            'author': {
                'id': user_id,
            },
            'status': 1 if program.is_active else 0
        }

    def _get_node_id(self, api_client, uuid):
        node_url = '{root}/node.json?field_uuid={uuid}'.format(root=api_client.api_url, uuid=uuid)
        response = api_client.api_session.get(node_url)
        if response.status_code == 200:
            found = response.json()
            if found:
                list_item = found.get('list')
                if list_item:
                    return list_item[0]['nid']

    def _edit_node(self, api_client, nid, node_data):
        if node_data.get('uuid'):
            # Drupal do not allow us to update the UUID field on node update
            del node_data['uuid']
        node_url = '{root}/node.json/{nid}'.format(root=api_client.api_url, nid=nid)
        response = api_client.api_session.put(node_url, data=json.dumps(node_data))
        if response.status_code != 200:
            raise ProgramPublisherException("Marketing site page edit failed!")

    def _create_node(self, api_client, node_data):
        node_url = '{root}/node.json'.format(root=api_client.api_url)
        response = api_client.api_session.post(node_url, data=json.dumps(node_data))
        if response.status_code == 201:
            return response.json()
        else:
            raise ProgramPublisherException("Marketing site page creation failed!")

    def publish_program(self, program):
        if not program.partner.has_marketing_site:
            return

        if not (program.partner.marketing_site_api_username and program.partner.marketing_site_api_password):
            msg = 'Marketing Site API credentials are not properly configured for Partner [{partner}]!'.format(
                partner=program.partner.short_code)
            raise ProgramPublisherException(msg)

        if self.data_before and \
                self.data_before.get('title') == program.title and \
                self.data_before.get('status') == program.status and \
                self.data_before.get('type') == program.type:
            # We don't need to publish to marketing site because
            # nothing we care about has changed. This would save at least 4 network calls
            return

        api_client = MarketingSiteAPIClient(
            program.partner.marketing_site_api_username,
            program.partner.marketing_site_api_password,
            program.partner.marketing_site_url_root
        )

        node_data = self._get_node_data(program, api_client.user_id)
        nid = self._get_node_id(api_client, program.uuid)
        if nid:
            # We would like to edit the existing node
            self._edit_node(api_client, nid, node_data)
        else:
            # We should create a new node
            self._create_node(api_client, node_data)
