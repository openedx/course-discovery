""" Data loaders. """
import abc
import logging

from edx_rest_api_client.client import EdxRestApiClient

from course_discovery.apps.course_metadata.models import Organization, Image

logger = logging.getLogger(__name__)


class AbstractDataLoader(metaclass=abc.ABCMeta):
    """ Base class for all data loaders.

    Attributes:
        api_url (str): URL of the API from which data is loaded
        access_token (str): OAuth2 access token
        PAGE_SIZE (int): Number of items to load per API call
    """

    PAGE_SIZE = 50

    def __init__(self, api_url, access_token):
        """
        Arguments:
            api_url (str): URL of the API from which data is loaded
            access_token (str): OAuth2 access token
        """
        self.access_token = access_token
        self.api_url = api_url

    @abc.abstractmethod
    def ingest(self):  # pragma: no cover
        """ Load data for all supported objects (e.g. courses, runs). """
        pass

    def clean_strings(self, data):
        """ Iterates over all string values, removing leading and trailing spaces,
        and replacing empty strings with None. """
        return {k: v.strip() or None for k, v in data.items() if isinstance(v, str)}


class OrganizationsApiDataLoader(AbstractDataLoader):
    """ Loads organizations from the Organizations API. """

    def ingest(self):
        client = EdxRestApiClient(self.api_url, oauth_access_token=self.access_token)
        count = None
        page = 1

        logger.info('Refreshing Organizations from %s....', self.api_url)

        while page:
            response = client.organizations().get(page=page, page_size=self.PAGE_SIZE)
            count = response['count']
            results = response['results']
            logger.info('Retrieved %d organizations...', len(results))

            if response['next']:
                page += 1
            else:
                page = None

            for body in results:
                body = self.clean_strings(body)
                self.update_organization(body)

        logger.info('Retrieved %d organizations from %s.', count, self.api_url)

    def update_organization(self, body):
        image = None
        image_url = body['logo']

        if image_url:
            image_url = image_url.lower()
            image, __ = Image.objects.get_or_create(src=image_url)

        defaults = {
            'name': body['name'],
            'description': body['description'],
            'logo_image': image,
        }

        Organization.objects.update_or_create(key=body['short_name'], defaults=defaults)
