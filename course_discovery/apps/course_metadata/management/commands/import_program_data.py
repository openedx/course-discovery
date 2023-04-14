"""
Management command to import program data for external products.
"""
import csv
import logging

import unicodecsv
from django.apps import apps
from django.conf import settings
from django.core.management import BaseCommand, CommandError
from django.db.models.signals import post_delete, post_save

from course_discovery.apps.api.cache import api_change_receiver
from course_discovery.apps.course_metadata.gspread_client import GspreadClient
from course_discovery.apps.course_metadata.models import (
    Program, ProgramDataLoaderConfiguration, ProgramSubscription, ProgramSubscriptionPrice, Source
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Import programs from a CSV available either through a provided csv file path ' \
           'or a CSV file uploaded through ProgramDataLoaderConfiguration in django admin.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--csv_path',
            help='Path to the CSV file',
            type=str,
        )

        parser.add_argument(
            '--args_from_env',
            help='Link to the Data Spreadsheet',
            type=bool,
        )
        parser.add_argument(
            '--product_type',
            help='Product Type to ingest',
            type=str,
            default='PROGRAMS',
            choices=['PROGRAMS']
        )
        parser.add_argument(
            '--product_source',
            help='Slug of product source with which ingested degrees are to be linked.',
            type=str,
            required=True
        )

    def handle(self, *args, **options):
        """
        Example usage: ./manage.py import_program_data --csv_path=test.csv
        """
        csv_path = options.get('csv_path', None)
        program_loader_config = ProgramDataLoaderConfiguration.current()
        csv_file = program_loader_config.csv_file if program_loader_config.is_enabled() else None
        args_from_env = options.get('args_from_env', None)
        product_type = options.get('product_type', None)
        product_source = options.get('product_source', None)

        try:
            source = Source.objects.get(slug=product_source)
        except Source.DoesNotExist:
            raise CommandError(  # pylint: disable=raise-missing-from
                "Unable to locate Product Source with code {}".format(product_source)
            )

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
                product_config = settings.PRODUCT_METADATA_MAPPING[product_type][source.slug]
                gspread_client = GspreadClient()
                reader = gspread_client.read_data(product_config)

            else:
                # Read file from the path if given. Otherwise,
                # read from the file received from ProgramDataLoaderConfiguration.
                reader = csv.DictReader(open(csv_path, 'r')) if csv_path \
                    else list(unicodecsv.DictReader(csv_file))  # lint-amnesty, pylint: disable=consider-using-with
        except FileNotFoundError:
            logger.exception("Error opening csv file at path %s", csv_path)
            raise  # re-raising exception to avoid moving the code flow
        except Exception:
            logger.exception("Error reading the input data source")
            raise  # re-raising exception to avoid moving the code flow

        reader = list(reader)

        logger.info("Initiating Program CSV data loader flow.")
        for row in reader:
            row = self.transform_dict_keys(row)
            program_uuid = row.get('uuid', None)
            price = int(row.get('subscription_price', None).strip('$'))
            try:
                program = Program.objects.get(uuid=program_uuid)
                subscription, _ = ProgramSubscription.objects.update_or_create(
                    program=program, subscription_eligible=True
                )
                subscription_price, _ = ProgramSubscriptionPrice.objects.update_or_create(
                    program_subscription=subscription, price=price
                )
                logger.info('Program located with slug: %s. Created its subscription with price: %s USD',
                            program.marketing_slug, subscription_price.price)
            except Program.DoesNotExist:
                raise CommandError(  # pylint: disable=raise-missing-from
                    "Unable to locate Program instance with code {}".format(program_uuid)
                )

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
