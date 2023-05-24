"""
Management command to import, create, and/or update degrees' data.
"""
import logging

from django.core.management import BaseCommand, CommandError

from course_discovery.apps.core.models import Partner
from course_discovery.apps.course_metadata.data_loaders.product_value_loader import ProductValueCSVDataLoader
from course_discovery.apps.course_metadata.models import ProductValueDataLoaderConfiguration

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Import product value information from a CSV available either through a provided csv file path ' \
           'or a CSV file uploaded through ProductValueDataLoaderConfiguration in django admin.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--csv_path',
            help='Path to the CSV file',
            type=str,
        )

    def handle(self, *args, **options):
        """
        Example usage: ./manage.py import_product_value_data --csv_path=test.csv
        """
        product_value_loader_config = ProductValueDataLoaderConfiguration.current()
        csv_path = options.get('csv_path', None)
        csv_file = product_value_loader_config.csv_file if product_value_loader_config.is_enabled() else None

        try:
            partner = Partner.objects.get(short_code='edx')
        except Partner.DoesNotExist:
            raise CommandError(  # pylint: disable=raise-missing-from
                "Unable to locate partner with code {}".format('edx')
            )

        try:
            loader = ProductValueCSVDataLoader(partner, csv_path=csv_path, csv_file=csv_file)
            logger.info("Starting Product Value CSV loader import")
            loader.ingest()
        except Exception as exc:
            raise CommandError(  # pylint: disable=raise-missing-from
                "Product Value CSV loader import could not be completed due to unexpected errors.\n{}".format(exc)
            )
        logger.info("Product Value CSV loader import flow completed.")
