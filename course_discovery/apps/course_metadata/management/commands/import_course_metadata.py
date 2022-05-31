"""
Management command to import, create, and/or update course and course run information for
executive education courses.
"""
import logging

from django.apps import apps
from django.core.management import BaseCommand, CommandError
from django.db.models.signals import post_delete, post_save

from course_discovery.apps.api.cache import api_change_receiver, set_api_timestamp
from course_discovery.apps.core.models import Partner
from course_discovery.apps.course_metadata.data_loaders.csv_loader import CSVDataLoader
from course_discovery.apps.course_metadata.signals import connect_api_change_receiver

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Import course and course run information from a CSV available on a provided csv path.'

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
            required=True
        )

    def handle(self, *args, **options):
        """
        Example usage: ./manage.py import_course_metadata --partner_code=edx --csv_path=test.csv
        """
        partner_short_code = options.get('partner_code')
        csv_path = options.get('csv_path')
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
            loader = CSVDataLoader(partner, csv_path=csv_path)
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
