"""
Management command to import, create, and/or update degrees' data.
"""
import logging

from django.apps import apps
from django.core.management import BaseCommand, CommandError
from django.db.models.signals import post_delete, post_save

from course_discovery.apps.api.cache import api_change_receiver, set_api_timestamp
from course_discovery.apps.core.models import Partner
from course_discovery.apps.course_metadata.data_loaders.degrees_loader import DegreeCSVDataLoader
from course_discovery.apps.course_metadata.models import DegreeDataLoaderConfiguration
from course_discovery.apps.course_metadata.signals import connect_api_change_receiver

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Import degree information from a CSV available either through a provided csv file path ' \
           'or a CSV file uploaded through DegreeDataLoaderConfiguration in django admin.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--partner_code',
            help='The short code for a specific partner to import degree to, defaults to "edx".',
            default='edx',
            type=str,
        )
        parser.add_argument(
            '--csv_path',
            help='Path to the CSV file',
            type=str,
        )
        parser.add_argument(
            '--product_type',
            help='Product Type to ingest',
            type=str,
            default='DEGREES',
            choices=['DEGREES']
        )
        parser.add_argument(
            '--args_from_env',
            help='Link to the Data Spreadsheet',
            type=bool,
        )

    def handle(self, *args, **options):
        """
        Example usage: ./manage.py import_degree_data --partner_code=edx --csv_path=test.csv
        """
        partner_short_code = options.get('partner_code')
        degree_loader_config = DegreeDataLoaderConfiguration.current()
        csv_path = options.get('csv_path', None)
        csv_file = degree_loader_config.csv_file if degree_loader_config.is_enabled() else None
        product_type = options.get('product_type', None)
        args_from_env = options.get('args_from_env', None)

        try:
            partner = Partner.objects.get(short_code=partner_short_code)
        except Partner.DoesNotExist:
            raise CommandError(  # pylint: disable=raise-missing-from
                "Unable to locate partner with code {}".format(partner_short_code)
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
            loader = DegreeCSVDataLoader(
                partner, csv_path=csv_path, csv_file=csv_file,
                args_from_env=args_from_env, product_type=product_type
            )
            logger.info("Starting CSV loader import flow for partner {}".format(partner_short_code))  # lint-amnesty, pylint: disable=logging-format-interpolation
            loader.ingest()
        except Exception as exc:
            raise CommandError(  # pylint: disable=raise-missing-from
                "CSV loader import could not be completed due to unexpected errors.\n{}".format(exc)
            )
        else:
            set_api_timestamp()
            logger.info("CSV loader import flow completed.")
        finally:
            # Re-connect back the api_change_receiver receiver to post_save and post_delete signals
            connect_api_change_receiver()
