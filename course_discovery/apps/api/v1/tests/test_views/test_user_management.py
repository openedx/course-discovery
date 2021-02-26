import json
from unittest import mock

import ddt
from django.urls import reverse

from course_discovery.apps.api.tests.jwt_utils import generate_jwt_header_for_user
from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase
from course_discovery.apps.core.tests.factories import UserFactory

JSON_CONTENT_TYPE = 'application/json'


@ddt.ddt
@mock.patch('django.conf.settings.USERNAME_REPLACEMENT_WORKER', 'test_replace_username_service_worker')
class UsernameReplacementViewTests(APITestCase):
    """ Tests UsernameReplacementView """
    SERVICE_USERNAME = 'test_replace_username_service_worker'

    def setUp(self):
        super().setUp()
        self.service_user = UserFactory(username=self.SERVICE_USERNAME)
        self.url = reverse("api:v1:replace_usernames")

    def build_jwt_headers(self, user):
        """
        Helper function for creating headers for the JWT authentication.
        """
        token = generate_jwt_header_for_user(user)
        headers = {'HTTP_AUTHORIZATION': token}
        return headers

    def call_api(self, user, data):
        """ Helper function to call API with data """
        data = json.dumps(data)
        headers = self.build_jwt_headers(user)
        return self.client.post(self.url, data, content_type=JSON_CONTENT_TYPE, **headers)

    def test_auth(self):
        """ Verify the endpoint only works with the service worker """
        data = {
            "username_mappings": [
                {"test_username_1": "test_new_username_1"},
                {"test_username_2": "test_new_username_2"}
            ]
        }

        # Test unauthenticated
        response = self.client.post(self.url)
        assert response.status_code == 401

        # Test non-service worker
        random_user = UserFactory()
        response = self.call_api(random_user, data)
        assert response.status_code == 403

        # Test service worker
        response = self.call_api(self.service_user, data)
        assert response.status_code == 200

    @ddt.data(
        [{}, {}],
        {},
        [{"test_key": "test_value", "test_key_2": "test_value_2"}]
    )
    def test_bad_schema(self, mapping_data):
        """ Verify the endpoint rejects bad data schema """
        data = {
            "username_mappings": mapping_data
        }
        response = self.call_api(self.service_user, data)
        assert response.status_code == 400

    def test_existing_and_non_existing_users(self):
        """
        Tests a mix of existing and non existing users. Users that don't exist
        in this service are also treated as a success because no work needs to
        be done changing their username.
        """
        random_users = [UserFactory() for _ in range(5)]
        fake_usernames = ["myname_" + str(x) for x in range(5)]
        existing_users = [{user.username: user.username + '_new'} for user in random_users]
        non_existing_users = [{username: username + '_new'} for username in fake_usernames]
        data = {
            "username_mappings": existing_users + non_existing_users
        }
        expected_response = {
            'failed_replacements': [],
            'successful_replacements': existing_users + non_existing_users
        }
        response = self.call_api(self.service_user, data)
        assert response.status_code == 200
        assert response.data == expected_response
