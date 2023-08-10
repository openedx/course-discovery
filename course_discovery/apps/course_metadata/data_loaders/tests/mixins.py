from unittest import mock

import responses

from course_discovery.apps.api.v1.tests.test_views.mixins import OAuth2Mixin
from course_discovery.apps.course_metadata.tests.factories import PartnerFactory


# pylint: disable=not-callable
class DataLoaderTestMixin(OAuth2Mixin):
    loader_class = None
    partner = None

    def setUp(self):
        super().setUp()
        self.partner = PartnerFactory(lms_url='http://127.0.0.1:8000')
        self.mock_access_token()
        with mock.patch(
            'course_discovery.apps.course_metadata.data_loaders.configured_jwt_decode_handler',
            return_value={'preferred_username': 'test_username'},
        ):
            self.loader = self.loader_class(self.partner, self.api_url)

    @property
    def api_url(self):  # pragma: no cover
        raise NotImplementedError

    def assert_api_called(self, expected_num_calls, check_auth=True):
        """ Asserts the API was called with the correct number of calls, and the appropriate Authorization header. """
        self.assertEqual(len(responses.calls), expected_num_calls)
        if check_auth:
            # 'JWT abcd' is the default value that comes from the mock_access_token function called in setUp
            self.assertEqual(responses.calls[1].request.headers['Authorization'], 'JWT abcd')

    def test_init(self):
        """ Verify the constructor sets the appropriate attributes. """
        self.assertEqual(self.loader.partner.short_code, self.partner.short_code)
