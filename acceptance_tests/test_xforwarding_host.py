""" Tests to validate X-Forwarded-Host is enable. """
import requests
from django.test import TestCase

from acceptance_tests.config import API_ACCESS_TOKEN, API_COURSES_ROOT


class XForwardedHostTest(TestCase):
    forwarded_host_name = 'api.stage.edx.org'
    path = 'api/v1/courses'

    def get_discovery_api_url(self, path):
        """ Returns a complete URL for the given path. """
        return '{root}/{path}'.format(root=API_COURSES_ROOT.rstrip('/'), path=path)

    def get_expected_paginated_url(self):
        return "http://{forwarded_host_name}/{path}/".format(forwarded_host_name=self.forwarded_host_name,
                                                             path=self.path)

    def assert_pagination_url(self, path, expected_status_code=200, **headers):
        """
        Verify the API returns HTTP 200 and next and previous pagination url
        generated with forwarded_host_name.

        Arguments:
            path(str) -- Path of the API endpoint to call.
            expected_status_code (int) -- Expected HTTP status code of the API response.
            headers (dict) -- Headers to pass with the request.
        """
        url = self.get_discovery_api_url(path)
        response = requests.get(url, headers=headers)
        courses_list = response.json()

        self.assertEqual(response.status_code, expected_status_code)

        if courses_list['next']:
            self.assertEqual(courses_list['next'].split('?')[0], self.get_expected_paginated_url())

        if courses_list['previous']:
            self.assertEqual(courses_list['previous'].split('?')[0], self.get_expected_paginated_url())

    def test_xforwarded_generated_pagination(self):
        """
        Verify the endpoint returns HTTP 200 for request and generates
        correct pagination url based on x-forwarded-host header param. """
        headers = {
            'Authorization': 'JWT {token}'.format(token=API_ACCESS_TOKEN),
            'X-Forwarded-Host': self.forwarded_host_name
        }
        self.assert_pagination_url(self.path, **headers)
