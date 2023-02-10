"""
API Client for LMS.
"""
import logging
from typing import Optional, Union
from urllib.parse import urlencode, urljoin

from django.conf import settings
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
        resource = settings.LMS_API_URLS['api_access_request']
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

    def _get_blocks_data(
        self,
        item_id: str,
        cache_key: str,
        query_parameters: Union[str, dict],
        resource: str,
        response_root_key: Optional[str] = None,
    ):
        """
        Helper function to fetch blocks based on given resourse and item_id.

        Args:
            item_id (str): course_id or block_id
            cache_key (str): cache key
            query_parameters (Union[str, dict]): query parameters for the request
            resource (str): resource url

        Returns:
            (dict): dict with xblock data
        """
        cached_blocks = cache.get(cache_key)

        if cached_blocks is SENTINEL_NO_RESULT:
            return None

        if cached_blocks:
            return cached_blocks

        blocks = None
        try:
            resource_url = urljoin(self.lms_url, resource)
            response = self.client.get(resource_url, params=query_parameters)
            response.raise_for_status()
            blocks = response.json()
            if response_root_key:
                blocks = blocks[response_root_key]
            if blocks:
                cache.set(cache_key, blocks, ONE_HOUR)
            else:
                cache.set(cache_key, SENTINEL_NO_RESULT, ONE_HOUR)
                logger.info('No blocks found for [%s].', item_id)

        except (RequestException, KeyError) as exception:
            cache.set(cache_key, SENTINEL_NO_RESULT, ONE_MINUTE)
            logger.exception('%s: Failed to fetch blocks from LMS for [%s].',
                             exception.__class__.__name__, item_id)

        return blocks

    def get_course_blocks_data(self, course_id: str, **kwargs):
        """
        Get all xblocks under a given course.

        Args:
            course_id (str): course key
            **kwargs: Can be used to pass additional query params to api

        Returns:
            (dict): dict with xblock data
        """
        resource = settings.LMS_API_URLS['blocks']
        query_parameters = {
            'course_id': course_id,
            'all_blocks': True,
            'depth': 'all',
            'requested_fields': 'children',
            **kwargs,
        }
        encoded_query_parameters = urlencode(query_parameters, safe=':')
        cache_key = get_cache_key(course_id=course_id, resource=resource)
        return self._get_blocks_data(
            course_id,
            cache_key,
            encoded_query_parameters,
            resource,
            response_root_key='blocks',
        )

    def get_blocks_data(self, block_id: str, **kwargs):
        """
        Get xblock data for given block_id or all blocks for given course_id.

        Args:
            block_id (str): usage key
            **kwargs: Can be used to pass additional query params to api

        Returns:
            (dict): dict with xblock data
        """
        resource = settings.LMS_API_URLS['blocks'] + block_id
        query_parameters = {
            'all_blocks': True,
            'depth': 'all',
            'requested_fields': 'children',
            **kwargs,
        }
        cache_key = get_cache_key(block_id=block_id, resource=resource)
        return self._get_blocks_data(block_id, cache_key, query_parameters, resource, response_root_key='blocks')

    def get_blocks_metadata(self, block_id: str, **kwargs):
        """
        Get xblock metadata for given block_id.

        Args:
            block_id (str): usage key
            **kwargs: Can be used to pass additional query params to api

        Returns:
            (dict): dict with xblock data
        """
        resource = settings.LMS_API_URLS['block_metadata'] + block_id
        query_parameters = {
            'include': 'index_dictionary',
            **kwargs,
        }
        cache_key = get_cache_key(block_id=block_id, resource=resource)
        return self._get_blocks_data(block_id, cache_key, query_parameters, resource)
