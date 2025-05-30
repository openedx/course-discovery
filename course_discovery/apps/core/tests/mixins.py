import json
import logging

import responses

logger = logging.getLogger(__name__)


class LMSAPIClientMixin(object):
    def mock_api_access_request(self, lms_url, user, status=200, api_access_request_overrides=None):
        """
        Mock the api access requests endpoint response of the LMS.
        """
        data = {
            'count': 2,
            'num_pages': 1,
            'current_page': 1,
            'results':
                [
                    dict(
                        {
                            'id': 1,
                            'created': '2017-09-25T08:37:05.872566Z',
                            'modified': '2017-09-25T08:37:47.412496Z',
                            'user': 1,
                            'status': 'approved',
                            'website': 'https://example.com/',
                            'reason': 'Example Reason',
                            'company_name': 'Test Company',
                            'company_address': 'Example Address',
                            'site': 1,
                            'contacted': True
                        },
                        **(api_access_request_overrides or {})
                    )
                ],
            'next': None,
            'start': 0,
            'previous': None
        }

        responses.add(
            responses.GET,
            lms_url.rstrip('/') + '/api-admin/api/v1/api_access_request/?user__username={}'.format(user.username),
            body=json.dumps(data),
            content_type='application/json',
            status=status
        )

    def mock_api_access_request_with_configurable_results(self, lms_url, user, status=200, results=None):
        """
        Mock the api access requests endpoint response of the LMS.
        """
        data = {
            'count': len(results),
            'num_pages': 1,
            'current_page': 1,
            'results': results,
            'next': None,
            'start': 0,
            'previous': None
        }

        responses.add(
            responses.GET,
            lms_url.rstrip('/') + '/api-admin/api/v1/api_access_request/?user__username={}'.format(user.username),
            body=json.dumps(data),
            content_type='application/json',
            status=status
        )

    def mock_api_access_request_with_invalid_data(self, lms_url, user, status=200, response_overrides=None):
        """
        Mock the api access requests endpoint response of the LMS.
        """
        data = response_overrides or {}

        responses.add(
            responses.GET,
            lms_url.rstrip('/') + '/api-admin/api/v1/api_access_request/?user__username={}'.format(user.username),
            body=json.dumps(data),
            content_type='application/json',
            status=status
        )
