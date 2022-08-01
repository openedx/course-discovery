import logging

import requests
from django.conf import settings
from django.core.cache import cache
from rest_framework import views
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

logger = logging.getLogger(__name__)


def exchange_rate_cache_key(*args, **kwargs):
    return 'exchange_rate_key'


class CurrencyView(views.APIView):
    permission_classes = (IsAuthenticated,)
    EXTERNAL_API_URL = 'https://openexchangerates.org/api/latest.json'

    def get_rates(self):
        app_id = settings.OPENEXCHANGERATES_API_KEY
        cache_key = exchange_rate_cache_key()

        if not app_id:
            logger.warning('Unable to retrieve exchange rate data. No API key is set.')
            return {}

        # Return cached response instead of making API call
        cached_rates = cache.get(cache_key)
        if cached_rates:
            logger.info("Using cached exchange rates data and skipping API call")
            return cached_rates

        try:
            response = requests.get(self.EXTERNAL_API_URL, params={'app_id': app_id}, timeout=2)

            if response.status_code == requests.codes.ok:  # pylint: disable=no-member
                response_json = response.json()
                rates = response_json['rates']
                # cache exchange rate API response for one day
                cache.set(exchange_rate_cache_key(), rates, timeout=60 * 60 * 24)
                return response_json['rates']
            else:
                logger.error(
                    'Failed to retrieve exchange rates from [%s]. Status: [%d], Body: %s',
                    self.EXTERNAL_API_URL, response.status_code, response.content)
        except Exception:  # pylint: disable=broad-except
            logger.exception('An error occurred while requesting exchange rates from [%s]', self.EXTERNAL_API_URL)

        return {}

    def get_data(self):
        rates = self.get_rates()
        # ISO 3166-1 alpha-3 codes
        currencies = {
            'IND': {'code': 'INR', 'symbol': '₹'},
            'BRA': {'code': 'BRL', 'symbol': 'R$'},
            'MEX': {'code': 'MXN', 'symbol': '$'},
            'GBR': {'code': 'GBP', 'symbol': '£'},
            'AUS': {'code': 'AUD', 'symbol': '$'},
            'CHN': {'code': 'CNY', 'symbol': '¥'},
            'COL': {'code': 'COP', 'symbol': '$'},
            'PER': {'code': 'PEN', 'symbol': 'S/.'},
            'CAN': {'code': 'CAD', 'symbol': '$'}
        }
        eurozone_countries = [
            'AUT', 'BEL', 'CYP', 'EST', 'FIN', 'FRA', 'DEU', 'GRC', 'IRL',
            'ITA', 'LVA', 'LTU', 'LUX', 'MLT', 'NLD', 'PRT', 'SVK', 'SVN', 'ESP'
        ]
        return [rates, currencies, eurozone_countries]

    def get(self, request, *_args, **_kwargs):
        rates, currencies, eurozone_countries = self.get_data()
        if not rates:
            return Response({})

        for country, currency in currencies.items():
            currency_name = currency['code']
            currencies[country]['rate'] = rates.get(currency_name)  # lint-amnesty, pylint: disable=unnecessary-dict-index-lookup

        eurozone_data = {'code': 'EUR', 'symbol': '€', 'rate': rates.get('EUR')}
        for country in eurozone_countries:
            currencies[country] = eurozone_data

        return Response(currencies)
