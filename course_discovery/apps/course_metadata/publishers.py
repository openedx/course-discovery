import json
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from django.utils.text import slugify

from course_discovery.apps.course_metadata.choices import CourseRunStatus
from course_discovery.apps.course_metadata.exceptions import (
    AliasCreateError,
    AliasDeleteError,
    FormRetrievalError,
    NodeCreateError,
    NodeDeleteError,
    NodeEditError,
    NodeLookupError
)
from course_discovery.apps.course_metadata.utils import MarketingSiteAPIClient


class BaseMarketingSitePublisher:
    """
    Utility for publishing data to a Drupal marketing site.

    Arguments:
        partner (apps.core.models.Partner): Partner instance containing information
            about the marketing site to which to publish.
    """
    unique_field = None
    node_lookup_field = None

    def __init__(self, partner):
        self.partner = partner

        self.client = MarketingSiteAPIClient(
            self.partner.marketing_site_api_username,
            self.partner.marketing_site_api_password,
            self.partner.marketing_site_url_root
        )

        self.node_api_base = urljoin(self.client.api_url, '/node.json')

    def publish_obj(self, obj, previous_obj=None):
        """
        Update or create a Drupal node corresponding to the given model instance.

        Arguments:
            obj (django.db.models.Model): Model instance to be published.

        Keyword Arguments:
            previous_obj (CourseRun): Model instance representing the previous
                state of the model being changed. Inspected to determine if publication
                is necessary. May not exist if the model instance is being saved
                for the first time.
        """
        raise NotImplementedError

    def delete_obj(self, obj):
        """
        Delete a Drupal node corresponding to the given model instance.

        Arguments:
            obj (django.db.models.Model): Model instance to be deleted.
        """
        node_id = self.node_id(obj)

        self.delete_node(node_id)

    def serialize_obj(self, obj):
        """
        Serialize a model instance to a representation that can be written to Drupal.

        Arguments:
            obj (django.db.models.Model): Model instance to be published.

        Returns:
            dict: Data to PUT to the Drupal API.
        """
        return {
            self.node_lookup_field: str(getattr(obj, self.unique_field)),
            'author': {'id': self.client.user_id},
        }

    def node_id(self, obj):
        """
        Find the ID of the node we want to publish to, if it exists.

        Arguments:
            obj (django.db.models.Model): Model instance to be published.

        Returns:
            str: The node ID.

        Raises:
            NodeLookupError: If node lookup fails.
        """
        params = {
            self.node_lookup_field: getattr(obj, self.unique_field),
        }

        response = self.client.api_session.get(self.node_api_base, params=params)

        if response.status_code == 200:
            return response.json()['list'][0]['nid']
        else:
            raise NodeLookupError({'response_text': response.text, 'response_status': response.status_code})

    def create_node(self, node_data):
        """
        Create a Drupal node.

        Arguments:
            node_data (dict): Data to POST to Drupal for node creation.

        Returns:
            str: The ID of the created node.

        Raises:
            NodeCreateError: If the POST to Drupal fails.
        """
        node_data = json.dumps(node_data)

        response = self.client.api_session.post(self.node_api_base, data=node_data)

        if response.status_code == 201:
            return response.json()['id']
        else:
            raise NodeCreateError({'response_text': response.text, 'response_status': response.status_code})

    def edit_node(self, node_id, node_data):
        """
        Edit a Drupal node.

        Arguments:
            node_id (str): ID of the node to edit.
            node_data (dict): Fields to overwrite on the node.

        Raises:
            NodeEditError: If the PUT to Drupal fails.
        """
        node_url = '{base}/{node_id}'.format(base=self.node_api_base, node_id=node_id)
        node_data = json.dumps(node_data)

        response = self.client.api_session.put(node_url, data=node_data)

        if response.status_code != 200:
            raise NodeEditError(
                {
                    'node_id': node_id,
                    'response_text': response.text,
                    'response_status': response.status_code
                }
            )

    def delete_node(self, node_id):
        """
        Delete a Drupal node.

        Arguments:
            node_id (str): ID of the node to delete.

        Raises:
            NodeDeleteError: If the DELETE to Drupal fails.
        """
        node_url = '{base}/{node_id}'.format(base=self.node_api_base, node_id=node_id)

        response = self.client.api_session.delete(node_url)

        if response.status_code != 200:
            raise NodeDeleteError(
                {
                    'node_id': node_id,
                    'response_text': response.text,
                    'response_status': response.status_code
                }
            )


class CourseRunMarketingSitePublisher(BaseMarketingSitePublisher):
    """
    Utility for publishing course run data to a Drupal marketing site.
    """
    unique_field = 'key'
    node_lookup_field = 'field_course_id'

    def publish_obj(self, obj, previous_obj=None):
        """
        Publish a CourseRun to the marketing site.

        Publication only occurs if the CourseRun's status has changed.

        Arguments:
            obj (CourseRun): CourseRun instance to be published.

        Keyword Arguments:
            previous_obj (CourseRun): Previous state of the course run. Inspected to
                determine if publication is necessary. May not exist if the course run
                is being saved for the first time.
        """
        if previous_obj and obj.status != previous_obj.status:
            node_id = self.node_id(obj)
            node_data = self.serialize_obj(obj)

            self.edit_node(node_id, node_data)

    def serialize_obj(self, obj):
        """
        Serialize the CourseRun instance to be published.

        Arguments:
            obj (CourseRun): CourseRun instance to be published.

        Returns:
            dict: Data to PUT to the Drupal API.
        """
        data = super().serialize_obj(obj)

        return {
            **data,
            'status': 1 if obj.status == CourseRunStatus.Published else 0,
        }


class ProgramMarketingSitePublisher(BaseMarketingSitePublisher):
    """
    Utility for publishing program data to a Drupal marketing site.
    """
    unique_field = 'uuid'
    node_lookup_field = 'field_uuid'

    def __init__(self, partner):
        super().__init__(partner)

        self.alias_api_base = urljoin(self.client.api_url, '/admin/config/search/path')
        self.alias_add_url = '{}/add'.format(self.alias_api_base)

    def publish_obj(self, obj, previous_obj=None):
        """
        Publish a Program to the marketing site.

        Arguments:
            obj (Program): Program instance to be published.

        Keyword Arguments:
            previous_obj (Program): Previous state of the program. Inspected to
                determine if publication is necessary. May not exist if the program
                is being saved for the first time.
        """
        types_to_publish = {
            'XSeries',
            'MicroMasters',
            'Professional Certificate',
        }

        if obj.type.name in types_to_publish:
            node_data = self.serialize_obj(obj)

            node_id = None
            if not previous_obj:
                node_id = self.create_node(node_data)
            else:
                trigger_fields = (
                    'marketing_slug',
                    'status',
                    'title',
                    'type',
                )

                if any(getattr(obj, field) != getattr(previous_obj, field) for field in trigger_fields):
                    node_id = self.node_id(obj)
                    # Drupal does not allow modification of the UUID field.
                    node_data.pop('uuid', None)

                    self.edit_node(node_id, node_data)

            if node_id:
                self.get_and_delete_alias(slugify(obj.title))
                self.update_node_alias(obj, node_id, previous_obj)

    def serialize_obj(self, obj):
        """
        Serialize the Program instance to be published.

        Arguments:
            obj (Program): Program instance to be published.

        Returns:
            dict: Data to PUT to the Drupal API.
        """
        data = super().serialize_obj(obj)

        return {
            **data,
            'status': 1 if obj.is_active else 0,
            'title': obj.title,
            'type': str(obj.type).lower().replace(' ', '_'),
            'uuid': str(obj.uuid),
        }

    def update_node_alias(self, obj, node_id, previous_obj):
        """
        Update alias of the Drupal node corresponding to the given object.

        Arguments:
            obj (Program): Program instance to be published.
            node_id (str): The ID of the node corresponding to the object.
            previous_obj (Program): Previous state of the program. May be None.

        Raises:
            AliasCreateError: If there's a problem creating a new alias.
            AliasDeleteError: If there's a problem deleting an old alias.
        """
        new_alias = self.alias(obj)
        previous_alias = self.alias(previous_obj) if previous_obj else None
        new_alias_delete_path = self.alias_delete_path(self.get_alias_list_url(obj.marketing_slug))

        if new_alias != previous_alias or not new_alias_delete_path:
            # Delete old alias before saving the new one.
            if previous_obj and previous_obj.marketing_slug != obj.marketing_slug:
                self.get_and_delete_alias(previous_obj.marketing_slug)

            headers = {
                'content-type': 'application/x-www-form-urlencoded'
            }

            data = {
                **self.alias_form_inputs(self.alias_add_url),
                'alias': new_alias,
                'form_id': 'path_admin_form',
                'op': 'Save',
                'source': 'node/{}'.format(node_id),
            }

            response = self.client.api_session.post(self.alias_add_url, headers=headers, data=data)

            if response.status_code != 200:
                raise AliasCreateError

    def get_and_delete_alias(self, slug):
        """
        Get the URL alias for the provided slug and delete it if exists.

        Arguments:
            slug (str): slug for which URL alias has to be fetched.
        """
        alias_list_url = self.get_alias_list_url(slug)
        alias_delete_path = self.alias_delete_path(alias_list_url)
        if alias_delete_path:
            self.delete_alias(alias_delete_path)

    def delete_alias(self, alias_delete_path):
        """
        Delete the url alias for provided path
        """
        headers = {
            'content-type': 'application/x-www-form-urlencoded'
        }
        alias_delete_url = '{base}/{path}'.format(
            base=self.client.api_url,
            path=alias_delete_path.strip('/')
        )

        data = {
            **self.alias_form_inputs(alias_delete_url),
            'confirm': 1,
            'form_id': 'path_admin_delete_confirm',
            'op': 'Confirm'
        }

        response = self.client.api_session.post(alias_delete_url, headers=headers, data=data)

        if response.status_code != 200:
            raise AliasDeleteError

    def alias(self, obj):
        return '{type}/{slug}'.format(type=obj.type.slug, slug=obj.marketing_slug)

    def alias_form_inputs(self, url):
        """
        Scrape input values from the form used to modify Drupal aliases.

        Raises:
            FormRetrievalError: If there's a problem getting the form from Drupal.
        """
        response = self.client.api_session.get(url)

        if response.status_code != 200:
            raise FormRetrievalError

        html = BeautifulSoup(response.text, 'html.parser')

        return {
            field: html.find('input', {'name': field}).get('value')
            for field in ('form_build_id', 'form_token')
        }

    def alias_delete_path(self, url):
        """
        Scrape the path to which we need to POST to delete an alias from the form
        used to modify aliases.

        Raises:
            FormRetrievalError: If there's a problem getting the form from Drupal.
        """
        response = self.client.api_session.get(url)

        if response.status_code != 200:
            raise FormRetrievalError

        html = BeautifulSoup(response.text, 'html.parser')
        delete_element = html.select('.delete.last a')

        return delete_element[0].get('href') if delete_element else None

    def get_alias_list_url(self, slug):
        return '{base}/list/{slug}'.format(
            base=self.alias_api_base,
            slug=slug
        )
