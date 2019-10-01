import json
import logging

from course_discovery.apps.course_metadata.exceptions import PersonToMarketingException
from course_discovery.apps.course_metadata.utils import MarketingSiteAPIClient

logger = logging.getLogger(__name__)


class MarketingSitePeople:
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
            'field_person_slug': person.slug,
            'title': person.full_name,
            'type': 'person',
            'status': 1 if person.published else 0
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

    def _get_node_id_from_uuid(self, api_client, uuid):
        node_url = '{root}/node.json?uuid={uuid}'.format(root=api_client.api_url, uuid=uuid)
        response = api_client.api_session.get(node_url)
        if response.status_code == 200:
            response_json = response.json()
            person_list = response_json.get('list')
            return person_list[0].get('nid') if person_list else None
        else:
            logger.exception('Failed to update person node on marketing site [%s].', response.content)
            raise PersonToMarketingException("Marketing site Person page update failed!")

    def update_or_publish_person(self, person):
        api_client = self._get_api_client(person.partner)
        if api_client:
            node_data = self._get_node_data(person)
            node_id = self._get_node_id_from_uuid(api_client, person.uuid)
            if node_id:
                return self._update_node(api_client, node_id, node_data)
            else:
                node_data['uuid'] = str(person.uuid)
                return self._create_node(api_client, node_data)
        return None

    def delete_person(self, partner, node_id):
        api_client = self._get_api_client(partner)
        if api_client and node_id:
            self._delete_node(api_client, node_id)

    def delete_person_by_uuid(self, partner, person_uuid):
        api_client = self._get_api_client(partner)
        node_id = self._get_node_id_from_uuid(api_client, person_uuid)
        if node_id:
            self._delete_node(api_client, node_id)
        else:
            logger.info('Person with UUID [%s] does not exist on the marketing site', person_uuid)

    def _update_node(self, api_client, node_id, node_data):
        node_url = '{root}/node.json/{node_id}'.format(root=api_client.api_url, node_id=node_id)
        response = api_client.api_session.put(node_url, data=json.dumps(node_data))
        if response.status_code == 200:
            response_json = response.json()
            return response_json
        else:
            logger.exception('Failed to update person node on marketing site [%s].', response.content)
            raise PersonToMarketingException("Marketing site Person page update failed!")

    def _delete_node(self, api_client, node_id):
        node_url = '{root}/node.json/{node_id}'.format(root=api_client.api_url, node_id=node_id)
        api_client.api_session.delete(node_url)
