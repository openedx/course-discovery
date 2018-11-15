import logging

import requests
from django.conf import settings
from rest_framework import views
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_extensions.cache.decorators import cache_response

logger = logging.getLogger(__name__)


def exchange_rate_cache_key(*args, **kwargs):  # pylint: disable=unused-argument
    return 'exchange_rate_key'


class CurrencyView(views.APIView):
    permission_classes = (IsAuthenticated,)
    EXTERNAL_API_URL = 'https://openexchangerates.org/api/latest.json'

    def get_rates(self):
        app_id = settings.OPENEXCHANGERATES_API_KEY

        if not app_id:
            logger.warning('Unable to retrieve exchange rate data. No API key is set.')
            return {}

        try:
            response = requests.get(self.EXTERNAL_API_URL, params={'app_id': app_id}, timeout=2)

            if response.status_code == requests.codes.ok:  # pylint: disable=no-member
                response_json = response.json()
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

    # Cache exchange rates for 1 day
    @cache_response(60 * 60 * 24, key_func=exchange_rate_cache_key)
    def get(self, request, *args, **kwargs):
        rates, currencies, eurozone_countries = self.get_data()
        if not rates:
            return Response({})

        for country, currency in currencies.items():
            currency_name = currency['code']
            currencies[country]['rate'] = rates.get(currency_name)

        eurozone_data = {'code': 'EUR', 'symbol': '€', 'rate': rates.get('EUR')}
        for country in eurozone_countries:
            currencies[country] = eurozone_data

        return Response(currencies)
