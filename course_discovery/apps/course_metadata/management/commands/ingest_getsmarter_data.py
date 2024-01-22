"""
Management command to ingest executive education course data from a CSV file.
This command collectively calls the following commands:
    - populate_executive_education_data_csv
    - import_course_metadata
"""

import logging
import tempfile

from django.core.management import BaseCommand, CommandError, call_command

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Ingest executive education course data using GetSmarter API.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--product_source',
            help='Slug of product source with whom the ingested courses are to be linked.',
            type=str,
            required=True
        )

    def handle(self, *args, **options):
        """
        Fetch products data from the GetSmarter API to populate a CSV file and ingest the data from the CSV file.
        """
        product_source = options.get('product_source')
        try:
            with tempfile.NamedTemporaryFile(suffix='.csv') as csv_file:
                csv_path = csv_file.name
                logger.info(
                    'Populating executive education data CSV file at path: %s', csv_path)
                call_command('populate_executive_education_data_csv',
                             use_getsmarter_api_client=True, output_csv=csv_path, product_source=product_source)
                logger.info(
                    'Ingesting executive education data from CSV file at path: %s', csv_path)
                call_command('import_course_metadata', csv_path=csv_path,
                             product_type='EXECUTIVE_EDUCATION', product_source=product_source)
        except Exception as exc:
            raise CommandError(
                f'Error while ingesting executive education data from CSV file at: {csv_path} with exception: {exc}'
            ) from exc
