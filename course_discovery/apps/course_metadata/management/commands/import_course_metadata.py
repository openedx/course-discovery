"""
Management command to import, create, and/or update course and course run information for
executive education courses.
"""
import csv
import logging
from datetime import datetime

from django.apps import apps
from django.conf import settings
from django.core.management import BaseCommand, CommandError
from django.db.models.signals import post_delete, post_save

from course_discovery.apps.api.cache import api_change_receiver, set_api_timestamp
from course_discovery.apps.core.models import Partner
from course_discovery.apps.course_metadata.data_loaders.csv_loader import CSVDataLoader
from course_discovery.apps.course_metadata.emails import send_ingestion_email
from course_discovery.apps.course_metadata.models import CourseType, CSVDataLoaderConfiguration, Source
from course_discovery.apps.course_metadata.signals import connect_api_change_receiver

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Import course and course run information from a CSV uploaded through ' \
           'CSVDataLoaderConfiguration in django admin or on a provided csv path.'

    PRODUCT_TYPE_SLUG_MAP = {
        'EXECUTIVE_EDUCATION': CourseType.EXECUTIVE_EDUCATION_2U,
        'BOOTCAMPS': CourseType.BOOTCAMP_2U
    }

    def add_arguments(self, parser):
        parser.add_argument(
            '--partner_code',
            help='The short code for a specific partner to import courses to, defaults to "edx".',
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
            required=True,
            choices=['EXECUTIVE_EDUCATION', 'BOOTCAMPS']
        )
        parser.add_argument(
            '--product_source',
            help='Slug of product source with whom the ingested courses are to be linked.',
            type=str,
            required=True
        )
        parser.add_argument(
            '--use_gspread_client',
            help='Identify if the CSV information should be read from PRODUCT_METADATA_MAPPING settings',
            type=bool,
        )

    def handle(self, *args, **options):
        """
        Example usage: ./manage.py import_course_metadata --partner_code=edx --csv_path=test.csv
        """
        partner_short_code = options.get('partner_code')
        csv_loader_config = CSVDataLoaderConfiguration.current()
        csv_path = options.get('csv_path', None)
        csv_file = csv_loader_config.csv_file if csv_loader_config.is_enabled() else None
        product_type = options.get('product_type', None)
        product_source = options.get('product_source', None)
        use_gspread_client = options.get('use_gspread_client', None)

        try:
            partner = Partner.objects.get(short_code=partner_short_code)
            source = Source.objects.get(slug=product_source)
        except Partner.DoesNotExist:
            raise CommandError(  # pylint: disable=raise-missing-from
                "Unable to locate partner with code {}".format(partner_short_code)
            )
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

        products_json = []
        try:
            loader = CSVDataLoader(
                partner,
                csv_path=csv_path,
                csv_file=csv_file,
                use_gspread_client=use_gspread_client,
                product_type=self.PRODUCT_TYPE_SLUG_MAP[product_type],
                product_source=source.slug
            )
            if csv_path:
                with open(csv_path, mode='r', encoding='utf-8') as csv_file:
                    products_json = list(csv.DictReader(csv_file))

            logger.info("Starting CSV loader import flow for partner {}".format(partner_short_code))  # lint-amnesty, pylint: disable=logging-format-interpolation
            ingestion_time = datetime.now()
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

        if product_type:
            logger.info(f"Sending Ingestion stats email for product type {product_type}")
            email_subject = f"{source.name} - {product_type.replace('_', ' ').title()} Data Ingestion"
            product_mapping = settings.PRODUCT_METADATA_MAPPING[self.PRODUCT_TYPE_SLUG_MAP[product_type]][source.slug]
            to_users = product_mapping['EMAIL_NOTIFICATION_LIST']
            ingestion_details = {
                'ingestion_run_time': ingestion_time,
                **loader.get_ingestion_stats(),
                'products_json': products_json
            }
            send_ingestion_email(
                partner, email_subject, to_users, product_type, source, ingestion_details,
            )
