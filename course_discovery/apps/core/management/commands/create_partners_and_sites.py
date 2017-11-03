""" Creates sites and partners """

import logging

from django.contrib.sites.models import Site
from django.core.management import BaseCommand

from course_discovery.apps.core.models import Partner

logger = logging.getLogger(__name__)

SITES = {
    "mitxpro": {
        "partner_code": "mitxpro",
        "site": "mitxpro"
    },
    "hms": {
        "partner_code": "hms",
        "site": "hms"
    },
    "wharton": {
        "partner_code": "wharton",
        "site": "wharton"
    },
    "harvardx": {
        "partner_code": "harvardx",
        "site": "harvardx"
    },

}


class Command(BaseCommand):
    help = 'Create new sites and associated Partners.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dns-name',
            action='store',
            type=str,
            dest='dns_name',
            required=True,
            help='DNS name of sandbox.',
        )

    def handle(self, *args, **options):
        """ Creates or updates a Partner record. """
        dns_name = options['dns_name']

        for _, site_data in SITES.items():
            site = site_data['site']

            logger.info("dns_name: {dns_name}".format(dns_name=dns_name))

            site_obj, created = Site.objects.get_or_create(
                domain="{domain}-{dns_name}.sandbox.edx.org".format(domain=site, dns_name=dns_name),
                defaults={"name": site}
            )
            studio_url = "https://studio-{dns_name}.sandbox.edx.org".format(dns_name=dns_name)
            oidc_url_root = "https://{site}-{dns_name}.sandbox.edx.org/oauth2".format(site=site, dns_name=dns_name)
            oidc_key = "{dns_name}-discovery-key".format(dns_name=dns_name)
            oidc_secret = "{dns_name}-discovery-secret".format(dns_name=dns_name)
            courses_api_url = "https://{site}-{dns_name}.sandbox.edx.org/api/courses/v1/".format(
                site=site,
                dns_name=dns_name
            )
            ecommerce_api_url = "https://ecommerce-{site}-{dns_name}.sandbox.edx.org/".format(
                site=site,
                dns_name=dns_name
            )
            organizations_api_url = "https://{site}-{dns_name}.sandbox.edx.org/api/organizations/v0/".format(
                site=site,
                dns_name=dns_name
            )
            __, created = Partner.objects.update_or_create(
                short_code=site_data['partner_code'],
                defaults={
                    'site': site_obj,
                    'name': site_data['partner_code'],
                    'oidc_key': oidc_key,
                    'studio_url': studio_url,
                    'oidc_secret': oidc_secret,
                    'oidc_url_root': oidc_url_root,
                    'courses_api_url': courses_api_url,
                    'ecommerce_api_url': ecommerce_api_url,
                    'organizations_api_url': organizations_api_url
                }
            )

