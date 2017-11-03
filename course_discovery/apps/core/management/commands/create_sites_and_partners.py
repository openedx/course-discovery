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

        for _, site_data in SITES:
            partner_code = site_data['partner_code']
            site = site_data['site']

            site, created = Site.objects.get_or_create(
                domain="{domain}-{dns_name}.sandbox.edx.org".format(domain=site, dns_name=dns_name),
                defaults={"name": site}
            )

            if created:
                studio_url = "https://studio-{dns_name}.sandbox.edx.org".format(dns_name=dns_name)
                openid_url = "https://{site}-{dns_name}.sandbox.edx.org/oauth2".format(site=site, dns_name=dns_name)
                openid_key = "{dns_name}-discovery-key".format(dns_name=dns_name)
                openid_secret = "{dns_name}-discovery-secret".format(dns_name=dns_name)
                courses_api_url = "https://{site}-{dns_name}.sandbox.edx.org/api/courses/v1/".format(
                    site=site,
                    dns_name=dns_name
                )
                ecomm_url = "https://ecommerce-{site}-{dns_name}.sandbox.edx.org/".format(site=site, dns_name=dns_name)

                logger.info("-------------------------------------------")
                logger.info("partner: {partner}".format(partner=partner_code))
                logger.info("-------------------------------------------")
                logger.info("studio: {studio}".format(studio=studio_url))
                logger.info("openid_url: {openid_url}".format(openid_url=openid_url))
                logger.info("openid_key: {openid_key}".format(openid_key=openid_key))
                logger.info("openid_secret: {openid_secret}".format(openid_secret=openid_secret))
                logger.info("courses_api_url: {courses_api_url}".format(courses_api_url=courses_api_url))
                logger.info("ecomm_url: {ecomm_url}".format(ecomm_url=ecomm_url))
        #logger.info('Partner %s with code %s', 'created' if created else 'updated', partner_code)


