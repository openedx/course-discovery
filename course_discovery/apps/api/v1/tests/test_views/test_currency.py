import mock
import pytest
from django.core.cache import cache
from django.urls import reverse

from course_discovery.apps.api.v1.views.currency import CurrencyView


@pytest.mark.usefixtures('django_cache')
@pytest.mark.django_db
class TestCurrencyCurrencyView:
    list_path = reverse('api:v1:currency')

    def test_authentication_required(self, client):
        response = client.get(self.list_path)
        assert response.status_code == 401

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
