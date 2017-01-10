import json

from bs4 import BeautifulSoup
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
        admin_url = '{root}/admin'.format(root=self.api_url)
        can_access_admin = session.get(admin_url)
        if not (can_access_admin.status_code == 200 and response.url == expected_url):
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
    program_before = None

    def __init__(self, program_before=None):
        if program_before:
            self.program_before = program_before

    def _get_api_client(self, program):
        if not program.partner.has_marketing_site:
            return

        if not (program.partner.marketing_site_api_username and program.partner.marketing_site_api_password):
            msg = 'Marketing Site API credentials are not properly configured for Partner [{partner}]!'.format(
                partner=program.partner.short_code)
            raise ProgramPublisherException(msg)

        if program.type.name not in ['MicroMasters', 'Professional Certificate']:
            # We do not publish programs that are not MicroMasters or Professional Certificate to the Marketing Site
            return

        fields_that_trigger_publish = ['title', 'status', 'type', 'marketing_slug']
        if self.program_before and \
                all(getattr(self.program_before, key) == getattr(program, key) for key in fields_that_trigger_publish):
            # We don't need to publish to marketing site because
            # nothing we care about has changed. This would save at least 4 network calls
            return

        return MarketingSiteAPIClient(
            program.partner.marketing_site_api_username,
            program.partner.marketing_site_api_password,
            program.partner.marketing_site_url_root
        )

    def _get_node_data(self, program, user_id):
        return {
            'type': str(program.type).lower().replace(' ', '_'),
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
            list_item = response.json().get('list')
            if list_item:
                return list_item[0]['nid']

    def _edit_node(self, api_client, node_id, node_data):
        # Drupal does not allow us to update the UUID field on node update
        node_data.pop('uuid', None)
        node_url = '{root}/node.json/{node_id}'.format(root=api_client.api_url, node_id=node_id)
        response = api_client.api_session.put(node_url, data=json.dumps(node_data))
        if response.status_code != 200:
            raise ProgramPublisherException("Marketing site page edit failed!")

    def _create_node(self, api_client, node_data):
        node_url = '{root}/node.json'.format(root=api_client.api_url)
        response = api_client.api_session.post(node_url, data=json.dumps(node_data))
        if response.status_code == 201:
            response_json = response.json()
            return response_json['id']
        else:
            raise ProgramPublisherException("Marketing site page creation failed!")

    def _delete_node(self, api_client, node_id):
        node_url = '{root}/node.json/{node_id}'.format(root=api_client.api_url, node_id=node_id)
        api_client.api_session.delete(node_url)

    def _get_form_build_id_and_form_token(self, api_client, url):
        form_attributes = {}
        response = api_client.api_session.get(url)
        if response.status_code != 200:
            raise ProgramPublisherException('Marketing site alias form retrieval failed!')
        form = BeautifulSoup(response.text, 'html.parser')
        for field in ('form_build_id', 'form_token'):
            form_attributes[field] = form.find('input', {'name': field}).get('value')
        return form_attributes

    def _get_delete_alias_url(self, api_client, url):
        response = api_client.api_session.get(url)
        if response.status_code != 200:
            raise ProgramPublisherException('Marketing site alias form retrieval failed!')
        form = BeautifulSoup(response.text, 'html.parser')
        delete_element = form.select('.delete.last a')
        return delete_element[0].get('href') if delete_element else None

    def _get_headers(self):
        headers = {
            'content-type': 'application/x-www-form-urlencoded'
        }
        return headers

    def _make_alias(self, program):
        alias = '{program_type_slug}/{slug}'.format(program_type_slug=program.type.slug, slug=program.marketing_slug)
        return alias

    def _add_alias(self, api_client, node_id, alias, before_slug):
        base_aliases_url = '{root}/admin/config/search/path'.format(root=api_client.api_url)
        add_aliases_url = '{url}/add'.format(url=base_aliases_url)
        node_url = 'node/{node_id}'.format(node_id=node_id)

        data = {
            'source': node_url,
            'alias': alias,
            'form_id': 'path_admin_form',
            'op': 'Save'
        }
        form_attributes = self._get_form_build_id_and_form_token(api_client, add_aliases_url)
        data.update(form_attributes)
        headers = self._get_headers()
        response = api_client.api_session.post(add_aliases_url, headers=headers, data=data)
        if response.status_code != 200:
            raise ProgramPublisherException('Marketing site alias creation failed!')

        # Delete old alias after saving new one
        if before_slug:
            list_aliases_url = '{url}/list/{slug}'.format(url=base_aliases_url, slug=before_slug)
            delete_alias_url = self._get_delete_alias_url(api_client, list_aliases_url)
            if delete_alias_url:
                delete_alias_url = '{root}{url}'.format(root=api_client.api_url, url=delete_alias_url)
                data = {
                    "confirm": 1,
                    "form_id": "path_admin_delete_confirm",
                    "op": "Confirm"
                }
                form_attributes = self._get_form_build_id_and_form_token(api_client, delete_alias_url)
                data.update(form_attributes)
                response = api_client.api_session.post(delete_alias_url, headers=headers, data=data)
                if response.status_code != 200:
                    raise ProgramPublisherException('Marketing site alias deletion failed!')

    def publish_program(self, program):
        api_client = self._get_api_client(program)
        if api_client:
            node_data = self._get_node_data(program, api_client.user_id)
            node_id = self._get_node_id(api_client, program.uuid)
            if node_id:
                # We would like to edit the existing node
                self._edit_node(api_client, node_id, node_data)
            else:
                # We should create a new node
                node_id = self._create_node(api_client, node_data)
            before_alias = self._make_alias(self.program_before) if self.program_before else None
            new_alias = self._make_alias(program)
            before_slug = self.program_before.marketing_slug if self.program_before else None
            if not self.program_before or (before_alias != new_alias):
                self._add_alias(api_client, node_id, new_alias, before_slug)

    def delete_program(self, program):
        api_client = self._get_api_client(program)
        if api_client:
            node_id = self._get_node_id(api_client, program.uuid)
            if node_id:
                self._delete_node(api_client, node_id)
