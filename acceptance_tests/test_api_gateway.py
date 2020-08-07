""" Tests to validate configuration of the API gateway. """
import ddt
import requests
from django.test import TestCase

from acceptance_tests.config import API_ACCESS_TOKEN, API_GATEWAY_CATALOG_ROOT, CATALOG_ID


@ddt.ddt
class ApiGatewayTests(TestCase):
    PATHS = (
        'catalogs/',
        f'catalogs/{CATALOG_ID}/',
        f'catalogs/{CATALOG_ID}/courses/',
    )

    def get_discovery_api_gateway_url(self, path):
        """ Returns a complete URL for the given path, routed through the API gateway. """
        return '{root}/{path}'.format(root=API_GATEWAY_CATALOG_ROOT.rstrip('/'), path=path)

    def assert_api_response(self, path, expected_status_code=200, **headers):
        """
        Verify the API returns HTTP 200.

        Arguments:
            path(str) -- Path of the API endpoint to call.
            expected_status_code (int) -- Expected HTTP status code of the API response.
            headers (dict) -- Headers to pass with the request.
        """
        url = self.get_discovery_api_gateway_url(path)
        response = requests.get(url, headers=headers)
        self.assertEqual(response.status_code, expected_status_code)

    @ddt.data(*PATHS)
    def test_endpoint_ok(self, path):
        """ Verify the endpoint returns HTTP 200 for valid requests. """
        headers = {
            'Authorization': f'JWT {API_ACCESS_TOKEN}'
        }
        self.assert_api_response(path, **headers)

    @ddt.data(*PATHS)
    def test_endpoint_not_authorized(self, path):
        """ Verify the endpoint returns HTTP 403 for unauthorized requests. """
        self.assert_api_response(path, expected_status_code=403)
