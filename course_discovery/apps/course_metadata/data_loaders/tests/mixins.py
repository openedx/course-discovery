import responses
from edx_rest_api_client.auth import SuppliedJwtAuth
from edx_rest_api_client.client import EdxRestApiClient

from course_discovery.apps.course_metadata.tests.factories import PartnerFactory

ACCESS_TOKEN = 'secret'
ACCESS_TOKEN_TYPE = 'JWT'


class ApiClientTestMixin(object):
    def test_api_client(self):
        """ Verify the property returns an API client with the correct authentication. """
        loader = self.loader_class(self.partner, self.api_url, ACCESS_TOKEN, ACCESS_TOKEN_TYPE)
        client = loader.api_client
        self.assertIsInstance(client, EdxRestApiClient)
        # NOTE (CCB): My initial preference was to mock the constructor and ensure the correct auth arguments
        # were passed. However, that seems nearly impossible. This is the next best alternative. It is brittle, and
        # may break if we ever change the underlying request class of EdxRestApiClient.
        self.assertIsInstance(client._store['session'].auth, SuppliedJwtAuth)  # pylint: disable=protected-access


# pylint: disable=not-callable
class DataLoaderTestMixin(object):
    loader_class = None
    partner = None

    def setUp(self):
        super(DataLoaderTestMixin, self).setUp()
        self.partner = PartnerFactory()
        self.loader = self.loader_class(self.partner, self.api_url, ACCESS_TOKEN, ACCESS_TOKEN_TYPE)

    @property
    def api_url(self):  # pragma: no cover
        raise NotImplementedError

    def assert_api_called(self, expected_num_calls, check_auth=True):
        """ Asserts the API was called with the correct number of calls, and the appropriate Authorization header. """
        self.assertEqual(len(responses.calls), expected_num_calls)
        if check_auth:
            self.assertEqual(responses.calls[0].request.headers['Authorization'], 'JWT {}'.format(ACCESS_TOKEN))

    def test_init(self):
        """ Verify the constructor sets the appropriate attributes. """
        self.assertEqual(self.loader.partner.short_code, self.partner.short_code)
        self.assertEqual(self.loader.access_token, ACCESS_TOKEN)
        self.assertEqual(self.loader.token_type, ACCESS_TOKEN_TYPE.lower())
