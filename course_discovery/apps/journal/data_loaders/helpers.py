from decimal import Decimal
import logging

from course_discovery.apps.core.models import Currency
from course_discovery.apps.journal.models import Journal

logger = logging.getLogger(__name__)


class EcommerceJournalDataLoader():
    '''
    Data Loader to fetch Journal information from Ecommerce
    '''
    def __init__(self, ecomm_data_loader):
        self.journal_skus = []
        self.partner = ecomm_data_loader.partner
        self.api_client = ecomm_data_loader.api_client
        self.page_size = ecomm_data_loader.PAGE_SIZE
        self.ecomm_data_loader = ecomm_data_loader

    def request_journals(self, page):
        return self.api_client.products().get(page=page, page_size=self.page_size, product_class='Journal')

    def process_journals(self, response):
        results = response['results']
        logger.info('Retrieved %d journals...', len(results))

        for body in results:
            body = self.ecomm_data_loader.clean_strings(body)
            self.journal_skus.append(self.update_journal(body))

    def update_journal(self, body):
        """
        Argument:
            body (dict): journals data from ecommerce
        Returns:
            journal product sku if no exceptions, else None
        """
        attributes = {attribute['name']: attribute['value'] for attribute in body['attribute_values']}
        journal_uuid = attributes.get('UUID')
        title = body['title']
        key = journal_uuid  # TODO, either drop this or create another attribute on the ecommerce product class

        if body['stockrecords']:
            stock_record = body['stockrecords'][0]
        else:
            msg = 'journal product {pub} has no stockrecords'.format(pub=title)
            logger.warning(msg)
            return None

        try:
            currency_code = stock_record['price_currency']
            price = Decimal(stock_record['price_excl_tax'])
            sku = stock_record['partner_sku']
        except (KeyError, ValueError):
            msg = 'A necessary stockrecord field is missing or incorrectly set for journal {journal}'.format(
                journal=title
            )
            logger.warning(msg)
            return None

        try:
            currency = Currency.objects.get(code=currency_code)
        except Currency.DoesNotExist:
            msg = 'Could not find currency {code} while loading entitlement {entitlement} with sku {sku}'.format(
                code=currency_code, entitlement=title, sku=sku
            )
            logger.warning(msg)
            return None

        defaults = {
            'partner': self.partner,
            'uuid': journal_uuid,
            'key': key,
            'title': title,
            'price': price,
            'currency': currency,
            'sku': sku,
            'expires': self.ecomm_data_loader.parse_date(body['expires'])
        }

        msg = 'Creating journal {journal} with sku {sku} for partner {partner}'.format(
            journal=title, sku=sku, partner=self.partner
        )
        logger.info(msg)
        Journal.objects.update_or_create(defaults=defaults)
        return sku

    def delete_journals(self):
        '''
        Delete journal instances
        '''
        pubs_to_delete = Journal.objects.filter(
            partner=self.partner
        ).exclude(sku__in=self.journal_skus)

        for pub in pubs_to_delete:
            msg = 'Deleting journal with sku {sku} for partner {partner}'.format(
                sku=pub.sku, partner=pub.partner
            )
            logger.info(msg)
        pubs_to_delete.delete()
