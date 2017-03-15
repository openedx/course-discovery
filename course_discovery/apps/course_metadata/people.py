import json
import logging

from course_discovery.apps.course_metadata.exceptions import PersonToMarketingException
from course_discovery.apps.course_metadata.utils import MarketingSiteAPIClient

logger = logging.getLogger(__name__)


class MarketingSitePeople(object):
    """
    This will add the object data to marketing site
    """
    def _get_api_client(self, partner):
        return MarketingSiteAPIClient(
            partner.marketing_site_api_username,
            partner.marketing_site_api_password,
            partner.marketing_site_url_root
        )

    def _get_node_data(self, person):
        return {
            'field_person_first_middle_name': person['given_name'],
            'field_person_last_name': person['family_name'],
            'type': 'person',
        }

    def _create_node(self, api_client, node_data):
        node_url = '{root}/node.json'.format(root=api_client.api_url)
        response = api_client.api_session.post(node_url, data=json.dumps(node_data))
        if response.status_code == 201:
            response_json = response.json()
            return response_json
        else:
            logger.exception('Failed to create person node to marketing site [%s].', response.content)
            raise PersonToMarketingException("Marketing site Person page creation failed!")

    def publish_person(self, partner, person):
        api_client = self._get_api_client(partner)
        node_data = self._get_node_data(person)
        if api_client:
            return self._create_node(api_client, node_data)

    def delete_person(self, partner, node_id):
        api_client = self._get_api_client(partner)
        if api_client and node_id:
            self._delete_node(api_client, node_id)

    def _delete_node(self, api_client, node_id):
        node_url = '{root}/node.json/{node_id}'.format(root=api_client.api_url, node_id=node_id)
        api_client.api_session.delete(node_url)
