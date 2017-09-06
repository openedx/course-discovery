import logging

import requests
from django.conf import settings
from rest_framework import views
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_extensions.cache.decorators import cache_response


class CurrencyView(views.APIView):
    permission_classes = (IsAuthenticated,)

    def get_rates(self):
        try:
            app_id = settings.OPENEXCHANGERATES_API_KEY
            if app_id:
                url = 'https://openexchangerates.org/api/latest.json'
                response = requests.get(url, params={'app_id': app_id}, timeout=2)
                response_json = response.json()
                result = response_json['rates']
                return result
            else:
                logging.warning('No app id available for openexchangerates')
                return {}
        except Exception as e:  # pylint: disable=broad-except
            response_text = '' if not isinstance(response, object) else response.text
            message = 'Exception Type {}. Message {}. Response {}.'.format(
                type(e).__name__, e, response_text
            )
            logging.error('Could not retrieve rates from openexchangerates. ' + message)
            return {}

    def get_data(self):
        rates = self.get_rates()
        # ISO 3166-1 alpha-3 codes
        currencies = {
            'IND': {'code': 'INR', 'symbol': u'₹'},
            'BRA': {'code': 'BRL', 'symbol': 'R$'},
            'MEX': {'code': 'MXN', 'symbol': '$'},
            'GBR': {'code': 'GBP', 'symbol': u'£'},
            'AUS': {'code': 'AUD', 'symbol': '$'},
            'CHN': {'code': 'CNY', 'symbol': u'¥'},
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
    @cache_response(60 * 60 * 24)
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
