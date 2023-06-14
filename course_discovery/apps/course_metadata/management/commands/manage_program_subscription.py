"""
Management command to manage subscription for program(s)
"""
import logging
from decimal import Decimal

import unicodecsv
from django.apps import apps
from django.conf import settings
from django.core.management import BaseCommand, CommandError
from django.db.models.signals import post_delete, post_save

from course_discovery.apps.api.cache import api_change_receiver
from course_discovery.apps.core.models import Currency
from course_discovery.apps.course_metadata.gspread_client import GspreadClient
from course_discovery.apps.course_metadata.models import (
    Program, ProgramSubscription, ProgramSubscriptionConfiguration, ProgramSubscriptionPrice
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Import programs from a CSV available either through a provided csv file path ' \
           'or a CSV file uploaded through ProgramDataLoaderConfiguration in django admin.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--args_from_env',
            help='Link to the Data Spreadsheet',
            type=bool,
        )

    def handle(self, *args, **options):
        """
        Example usage: ./manage.py manage_program_subscription --args_from_env False
        """
        program_loader_config = ProgramSubscriptionConfiguration.current()
        csv_file = program_loader_config.csv_file if program_loader_config.is_enabled() else None
        args_from_env = options.get('args_from_env', None)

        # The signal disconnect has been taken from refresh_course_metadata management command.
        # We only want to invalidate the API response cache once data loading
        # completes. Disconnecting the api_change_receiver function from post_save
        # and post_delete signals prevents model changes during data loading from
        # repeatedly invalidating the cache.
        for model in apps.get_app_config('course_metadata').get_models():
            for signal in (post_save, post_delete):
                signal.disconnect(receiver=api_change_receiver, sender=model)

        try:
            if args_from_env:
                product_config = settings.SUBSCRIPTION_METADATA_MAPPING
                gspread_client = GspreadClient()
                reader = gspread_client.read_data(product_config)

            else:
                reader = list(unicodecsv.DictReader(csv_file))

        except Exception:
            raise CommandError(  # pylint: disable=raise-missing-from
                'Error reading the input data source'
            )

        logger.info('Initiating Program CSV data loader flow.')
        for row in reader:
            row = self.transform_dict_keys(row)
            program_uuid = row.get('uuid', None)

            price = Decimal(row.get('subscription_price', None).strip('$'))
            subscription_eligible = row.get('subscription_eligible', None)

            if subscription_eligible not in ['TRUE', 'FALSE']:
                logger.warning(f'Skipped record: {program_uuid} because of '
                               f'invalid subscription eligibility value')
                continue

            currency_code = row.get('currency', None)
            try:
                currency = Currency.objects.get(code=currency_code)
            except Currency.DoesNotExist:
                logger.warning(f'Could not find currency {currency_code} for program {program_uuid}')
                continue

            try:
                subscription_eligible = subscription_eligible == 'TRUE'
                program = Program.objects.get(uuid=program_uuid)
                default_params = {
                    'subscription_eligible': subscription_eligible
                }
                subscription, _ = ProgramSubscription.objects.update_or_create(
                    program=program, defaults=default_params
                )
                subscription_price, created = ProgramSubscriptionPrice.objects.update_or_create(
                    program_subscription=subscription, currency=currency, defaults={'price': price}
                )
                created_or_updated = 'created' if created else 'updated'
                logger.info(f'Program ({program_uuid}) located with slug: {program.marketing_slug} '
                            f'is marked {"eligible" if subscription_eligible else "ineligible"} '
                            f'for subscription and its price: {subscription_price.price} '
                            f'{currency_code} is {created_or_updated}')
            except Program.DoesNotExist:
                logger.exception(f'Unable to locate Program instance with code {program_uuid}')

    def transform_dict_keys(self, data):
        """
        Given a data dictionary, return a new dict that has its keys transformed to
        snake case. For example, Enrollment Track becomes enrollment_track.

        Each key is stripped of whitespaces around the edges, converted to lower case,
        and has internal spaces converted to _. This convention removes the dependency on CSV
        headers format(Enrollment Track vs Enrollment track) and makes code flexible to ignore
        any case sensitivity, among other things.
        """
        transformed_dict = {}
        for key, value in data.items():
            updated_key = key.strip().lower().replace(' ', '_')
            transformed_dict[updated_key] = value
        return transformed_dict
