from unittest import mock

import pytest
from django.core.cache import cache
from django.urls import reverse
from testfixtures import LogCapture

from course_discovery.apps.api.v1.views.currency import CurrencyView, exchange_rate_cache_key


@pytest.mark.usefixtures('django_cache')
@pytest.mark.django_db
class TestCurrencyCurrencyView:
    list_path = reverse('api:v1:currency')
    CURRENCY_LOGGER = 'course_discovery.apps.api.v1.views.currency'

    def test_authentication_required(self, client):
        response = client.get(self.list_path)
        assert response.status_code == 401

    def test_get(self, admin_client, django_cache, responses, settings):  # pylint: disable=unused-argument
        settings.OPENEXCHANGERATES_API_KEY = 'test'
        cache_key = exchange_rate_cache_key()

        rates = {
            'GBP': 0.766609,
            'CAD': 1.222252,
            'CNY': 6.514431,
            'EUR': 0.838891
        }
        expected = {
            'GBR': {'code': 'GBP', 'symbol': '£', 'rate': 0.766609},
            'CAN': {'code': 'CAD', 'symbol': '$', 'rate': 1.222252},
            'CHN': {'code': 'CNY', 'symbol': '¥', 'rate': 6.514431},
            'FRA': {'code': 'EUR', 'symbol': '€', 'rate': 0.838891}
        }

        responses.add(responses.GET, CurrencyView.EXTERNAL_API_URL, json={'rates': rates})

        assert cache.get(cache_key) is None
        with LogCapture(self.CURRENCY_LOGGER) as log_capture:
            response = admin_client.get(self.list_path)
            assert all(item in response.json().items() for item in expected.items())
            assert len(responses.calls) == 1
            # verify the exchange rate API response is cached
            assert cache.get(cache_key) is not None
            assert all(item in cache.get(cache_key).items() for item in rates.items())

            # Subsequent requests should hit the cache
            response = admin_client.get(self.list_path)
            assert all(item in response.json().items() for item in expected.items())
            assert len(responses.calls) == 1
            log_capture.check(
                (
                    self.CURRENCY_LOGGER,
                    'INFO',
                    'Using cached exchange rates data and skipping API call',
                )
            )

            # Clearing the cache should result in the external service being called again
            cache.clear()
            response = admin_client.get(self.list_path)
            assert all(item in response.json().items() for item in expected.items())
            assert len(responses.calls) == 2

    def test_get_without_api_key(self, admin_client, settings):
        settings.OPENEXCHANGERATES_API_KEY = None

        with mock.patch('course_discovery.apps.api.v1.views.currency.logger.warning') as mock_logger:
            response = admin_client.get(self.list_path)
            mock_logger.assert_called_with('Unable to retrieve exchange rate data. No API key is set.')
            assert response.status_code == 200
            assert response.json() == {}

    def test_get_with_external_error(self, admin_client, responses, settings):
        settings.OPENEXCHANGERATES_API_KEY = 'test'

        status = 500
        responses.add(responses.GET, CurrencyView.EXTERNAL_API_URL, json={}, status=status)

        with mock.patch('course_discovery.apps.api.v1.views.currency.logger.error') as mock_logger:
            response = admin_client.get(self.list_path)
            mock_logger.assert_called_with(
                'Failed to retrieve exchange rates from [%s]. Status: [%d], Body: %s',
                CurrencyView.EXTERNAL_API_URL, status, b'{}'
            )
            assert response.status_code == 200
            assert response.json() == {}
