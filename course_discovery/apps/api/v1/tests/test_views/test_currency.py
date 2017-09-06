import mock
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse

from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase
from course_discovery.apps.api.v1.views.currency import CurrencyView
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory


class CurrencyViewTests(APITestCase):
    list_path = reverse('api:v1:currency')

    def setUp(self):
        super(CurrencyViewTests, self).setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.request.user = self.user
        self.client.login(username=self.user.username, password=USER_PASSWORD)

        # Clear the cache between test cases, so they don't interfere with each other.
        cache.clear()

    def test_get(self):
        """ Verify the endpoint returns the right currency data and uses the cache. """
        rates = {"GBP": 0.766609, "CAD": 1.222252, "CNY": 6.514431, "EUR": 0.838891}
        currencies = {
            'GBR': {'code': 'GBP', 'symbol': u'£'},
            'CHN': {'code': 'CNY', 'symbol': u'¥'},
            'CAN': {'code': 'CAD', 'symbol': '$'}
        }
        eurozone_countries = ['FRA']
        get_data_return_value = [rates, currencies, eurozone_countries]

        expected = {
            "GBR": {"code": "GBP", "symbol": u"£", "rate": 0.766609},
            "CAN": {"code": "CAD", "symbol": "$", "rate": 1.222252},
            "CHN": {"code": "CNY", "symbol": u"¥", "rate": 6.514431},
            "FRA": {"code": "EUR", "symbol": "€", "rate": 0.838891}
        }

        with mock.patch.object(CurrencyView, 'get_data', return_value=get_data_return_value) as mock_get_rates:
            response = self.client.get(self.list_path)
            self.assertDictEqual(response.data, expected)
            self.assertEqual(mock_get_rates.call_count, 1)

            # next request hits the cache
            response = self.client.get(self.list_path)
            self.assertEqual(mock_get_rates.call_count, 1)

            # clearing the cache calls means the function gets called again
            cache.clear()
            response = self.client.get(self.list_path)
            self.assertEqual(mock_get_rates.call_count, 2)

    def test_no_api_key(self):
        response = self.client.get(self.list_path)
        self.assertEqual(response.json(), {})

    @override_settings(OPENEXCHANGERATES_API_KEY='test')
    def test_get_rates(self):
        def mocked_requests_get(*args, **kwargs):  # pylint: disable=unused-argument
            class MockResponse:
                def __init__(self, json_data, status_code, text):
                    self.json_data = json_data
                    self.status_code = status_code
                    self.text = text

                def json(self):
                    return self.json_data
            return MockResponse({"bad": "data"}, 500, "baddata")
        with mock.patch('course_discovery.apps.api.v1.views.currency.requests.get', side_effect=mocked_requests_get):
            response = self.client.get(self.list_path)
            response_json = response.json()
            self.assertEqual(response_json, {})
