""" Creates sites and partners """

import fnmatch
import json
import logging
import os

from django.contrib.sites.models import Site
from django.core.management import BaseCommand

from course_discovery.apps.core.models import Partner

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Creates Partners and their perspective Sites.
    """
    dns_name = None
    theme_path = None

    def add_arguments(self, parser):
        parser.add_argument(
            "--dns-name",
            type=str,
            help="Enter DNS name of sandbox.",
            required=True
        )

        parser.add_argument(
            "--theme-path",
            type=str,
            help="Enter theme directory path",
            required=True
        )

    def find(self, pattern, path):
        """
        Matches the given pattern in given path and returns the list of matching files.
        """
        result = []
        for root, _, files in os.walk(path):
            for name in files:
                if fnmatch.fnmatch(name, pattern):
                    result.append(os.path.join(root, name))
        return result

    def _get_site_partner_data(self):
        """
        Reads the json files from theme directory and returns the site partner data in JSON format.
        """
        site_data = {}
        for config_file in self.find('sandbox_configuration.json', self.theme_path):
            logger.info("Reading file from {file_name}".format(file_name=config_file))
            configuration_data = json.loads(
                json.dumps(
                    json.load(
                        open(config_file)
                    )
                ).replace("{dns_name}", self.dns_name)
            )['discovery_configuration']

            site_data[configuration_data['site_partner']] = {
                "site_domain": configuration_data['site_domain'],
                "partner_data": configuration_data['partner_data']
            }
        return site_data

    def handle(self, *args, **options):
        """
        Creates sites and partners.
        """
        self.dns_name = options['dns_name']
        self.theme_path = options['theme_path']

        logger.info("DNS name: '{dns_name}'".format(dns_name=self.dns_name))
        logger.info("Theme path: '{theme_path}'".format(theme_path=self.theme_path))

        all_sites = self._get_site_partner_data()
        for site_partner, site_partner_data in all_sites.items():
            partner_data = site_partner_data['partner_data']

            logger.info("Creating '{site}' Site".format(site=site_partner))
            site, _ = Site.objects.get_or_create(
                domain=site_partner_data['site_domain'],
                defaults={"name": site_partner}
            )
            logger.info("Successfully created {site} site".format(site=site_partner))
            partner_data['site'] = site

            logger.info("Creating '{partner}' Partner".format(partner=site_partner))
            Partner.objects.get_or_create(
                short_code=site_partner,
                defaults=partner_data
            )
            logger.info("Successfully created {partner} Partner".format(partner=site_partner))
