"""
API Client for LMS.
"""
import logging

from django.core.cache import cache
from edx_rest_api_client.client import EdxRestApiClient
from edx_rest_api_client.exceptions import SlumberBaseException
from requests.exceptions import ConnectionError, Timeout  # pylint: disable=redefined-builtin

from course_discovery.apps.api.utils import get_cache_key

logger = logging.getLogger(__name__)


class LMSAPIClient(object):
    """
    API Client for communication between discovery and LMS.
    """

    def __init__(self, site, user):
        self.site = site
        self.user = user
        self.client = EdxRestApiClient(self.site.partner.lms_url, oauth_access_token=user.access_token)

    def get_api_access_request(self, user):
        """
        Get API Access Requests made by the given user.

        Arguments:
            user (User): Django User.

        Returns:
            (dict): API Access requests made by the given user.

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
        query_parameters = {}

        # Since Staff user has access to all API Access Requests and we want to limit the response.
        # So, we will filter by username for staff users.
        if user.is_staff:
            query_parameters = {
                'user__username': user.username
            }

        cache_key = get_cache_key(username=user.username, resource=resource)
        api_access_request = cache.get(cache_key)

        if not api_access_request:
            try:
                results = getattr(self.client, resource).get(**query_parameters)['results']

                if len(results) > 1:
                    logger.warning(
                        'Multiple APIAccessRequest models returned from LMS API for user [%s].',
                        user.username,
                    )

                api_access_request = results[0]
                cache.set(cache_key, api_access_request, 60 * 60)
            except (SlumberBaseException, ConnectionError, Timeout):
                logger.exception('Failed to fetch API Access Request from LMS for user "%s".', user.username)
            except (IndexError, KeyError):
                # This should not happen as user must always have at-least one api-access-request.
                logger.exception('APIAccessRequest model not found for user [%s].', user.username)

        return api_access_request
