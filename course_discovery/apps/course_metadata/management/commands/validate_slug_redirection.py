"""
Management command to check and log the 404s responses in case of redirect
"""
import logging
from urllib.parse import urljoin

import requests
import unicodecsv
from django.conf import settings
from django.core.management import BaseCommand, CommandError

from course_discovery.apps.core.models import Partner
from course_discovery.apps.course_metadata.models import SlugRedirectionDataLoaderConfiguration

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Import slugs from the CSV file uploaded through SlugRedirectionDataLoaderConfiguration in django admin.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--partner_code',
            help='The short code for a specific partner to access its marketing url, defaults to "edx".',
            default='edx',
            type=str,
        )

    def handle(self, *args, **options):
        """
        Example usage: ./manage.py validate_slug_redirection
        """
        partner_shore_code = options.get('partner_code')
        slug_loader_config = SlugRedirectionDataLoaderConfiguration.current()
        csv_file = slug_loader_config.csv_file if slug_loader_config.is_enabled() else None

        try:
            partner = Partner.objects.get(short_code=partner_shore_code)

        except Partner.DoesNotExist:
            raise CommandError(  # pylint: disable=raise-missing-from
                f'Unable to locate partner with code {partner_shore_code}'
            )

        try:
            reader = list(unicodecsv.DictReader(csv_file))

        except Exception:
            raise CommandError(  # pylint: disable=raise-missing-from
                'Error reading the input data source'
            )

        logger.info('Initiating SlugRedirection CSV data loader flow.')
        for row in reader:
            old_slug = row.get('old_slug', None)
            new_slug = row.get('new_slug', None)

            old_url, _ = self.get_course_urls(partner, old_slug, new_slug)

            response = requests.get(old_url)
            log_msg = 'Redirected:' if len(response.history) > 0 else 'Not Redirected:'
            if response.ok:
                logger.info(f'{log_msg} Got the response from {response.url} in result of the request {old_url}')

            else:
                logger.error(f'Unable to get the response from {old_url} with status_code: {response.status_code} '
                             f'and reason: {response.reason}')

    def get_course_urls(self, partner, old_slug, new_slug):
        """
        Given the old and new course slugs and returns the relevant course urls based on slugs
        """
        old_url_path = f'course/{old_slug}'
        old_url = urljoin(partner.marketing_site_url_root, old_url_path)
        directory_based_url = urljoin(partner.marketing_site_url_root, new_slug)

        return old_url, directory_based_url
