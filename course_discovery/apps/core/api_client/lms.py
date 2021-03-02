"""
API Client for LMS.
"""
import logging
from urllib.parse import urljoin

from django.core.cache import cache
from edx_django_utils.cache import get_cache_key
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)

SENTINEL_NO_RESULT = ()
ONE_HOUR = 60 * 60
ONE_MINUTE = 60


class LMSAPIClient:
    """
    API Client for communication between discovery and LMS.
    """

    def __init__(self, partner):
        self.client = partner.oauth_api_client
        self.lms_url = partner.lms_url

    def get_api_access_request(self, user):
        """
        Get ApiAccessRequests made by the given user.

        Arguments:
            user (User): Django User.

        Returns:
            (dict): ApiAccessRequests for the given user.

        Examples:
            >> user = User.objects.get(username='staff')
            >> lms_api_client.get_api_access_requests(user)
            {
                "id": 1,
                "created": "2017-09-25T08:37:05.872566Z",
                "modified": "2017-09-25T08:37:47.412496Z",
                "user": 5,
                "status": "approved",
                "website": "https://example.com/",
                "reason": "Example Reason",
                "company_name": "Example Inc",
                "company_address": "Example Address",
                "site": 1,
                "contacted": True
            }
        """
        resource = 'api-admin/api/v1/api_access_request/'
        query_parameters = {
            'user__username': user.username
        }

        cache_key = get_cache_key(username=user.username, resource=resource)
        cached_api_access_request = cache.get(cache_key)

        if cached_api_access_request is SENTINEL_NO_RESULT:
            return None

        if cached_api_access_request:
            return cached_api_access_request

        api_access_request = None
        try:
            resource_url = urljoin(self.lms_url, resource)
            response = self.client.get(resource_url, params=query_parameters)
            response.raise_for_status()
            results = response.json()['results']
            if results:
                if len(results) > 1:
                    logger.warning(
                        'Multiple ApiAccessRequest models returned from LMS API for user [%s].',
                        user.username,
                    )
                api_access_request = results[0]
                cache.set(cache_key, api_access_request, ONE_HOUR)
            else:
                cache.set(cache_key, SENTINEL_NO_RESULT, ONE_HOUR)
                logger.info('No results for ApiAccessRequest for user [%s].', user.username)

        except (RequestException, KeyError) as exception:
            cache.set(cache_key, SENTINEL_NO_RESULT, ONE_MINUTE)
            logger.exception('%s: Failed to fetch ApiAccessRequest from LMS for user [%s].',
                             exception.__class__.__name__, user.username)

        return api_access_request
