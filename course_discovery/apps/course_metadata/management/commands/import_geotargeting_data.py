"""
Management command to import, create, and/or update degrees' data.
"""
import logging

from django.apps import apps
from django.core.management import BaseCommand, CommandError
from course_discovery.apps.core.models import Partner
from course_discovery.apps.course_metadata.data_loaders.geotargeting_loader import GeotargetingCSVDataLoader
from course_discovery.apps.course_metadata.models import GeotargetingDataLoaderConfiguration

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Import geotargeting information from a CSV available either through a provided csv file path ' \
           'or a CSV file uploaded through GeotargetingDataLoaderConfiguration in django admin.'

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

    def handle(self, *args, **options):
        """
        Example usage: ./manage.py import_geotargeting_data --partner_code=edx --csv_path=test.csv
        """
        partner_short_code = options.get('partner_code')
        geotargeting_loader_config = GeotargetingDataLoaderConfiguration.current()
        csv_path = options.get('csv_path', None)
        csv_file = geotargeting_loader_config.csv_file if geotargeting_loader_config.is_enabled() else None
        
        try:
            partner = Partner.objects.get(short_code=partner_short_code)
        except Partner.DoesNotExist:
            raise CommandError(  # pylint: disable=raise-missing-from
                "Unable to locate partner with code {}".format(partner_short_code)
            )

        try:
            loader = GeotargetingCSVDataLoader(partner, csv_path=csv_path, csv_file=csv_file)
            logger.info("Starting CSV loader import")
            loader.ingest()
        except Exception as exc:
            raise CommandError(  # pylint: disable=raise-missing-from
                "CSV loader import could not be completed due to unexpected errors.\n{}".format(exc)
            )
        else:
            logger.info("CSV loader import flow completed.")


