""" Creates or updates a Partner, including API information """

import logging

from django.contrib.sites.models import Site
from django.core.management import BaseCommand

from course_discovery.apps.core.models import Partner

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Create a new Partner, or update an existing Partner.'

    def add_arguments(self, parser):
        parser.add_argument('--site-id',
                            action='store',
                            type=int,
                            help='ID of the Site to update.')
        parser.add_argument('--site-domain',
                            action='store',
                            type=str,
                            required=True,
                            help='Site domain for the Partner')
        parser.add_argument('--code',
                            action='store',
                            dest='partner_code',
                            type=str,
                            required=True,
                            help='Short code for the specified Partner.')
        parser.add_argument('--name',
                            action='store',
                            dest='partner_name',
                            type=str,
                            required=True,
                            help='Name for the specified Partner.')
        parser.add_argument('--courses-api-url',
                            action='store',
                            type=str,
                            default='',
                            help='API endpoint for accessing Partner course data.')
        parser.add_argument('--lms-coursemode-api-url',
                            action='store',
                            type=str,
                            default='',
                            help='API endpoint for accessing Partner course mode data.')
        parser.add_argument('--ecommerce-api-url',
                            action='store',
                            type=str,
                            default='',
                            help='API endpoint for accessing Partner ecommerce data.')
        parser.add_argument('--organizations-api-url',
                            action='store',
                            type=str,
                            default='',
                            help='API endpoint for accessing Partner organization data.')
        parser.add_argument('--programs-api-url',
                            action='store',
                            type=str,
                            default='',
                            help='API endpoint for accessing Partner program data.')
        parser.add_argument('--lms-url',
                            action='store',
                            type=str,
                            default='',
                            help='API endpoint for accessing lms.')
        parser.add_argument('--studio-url',
                            action='store',
                            type=str,
                            default='',
                            help='API endpoint for accessing studio.')
        parser.add_argument('--publisher-url',
                            action='store',
                            type=str,
                            default='',
                            help='API endpoint for accessing Publisher.')
        parser.add_argument('--marketing-site-api-url',
                            action='store',
                            type=str,
                            default='',
                            help='API endpoint for accessing Partner marketing site data.')
        parser.add_argument('--marketing-site-url-root',
                            action='store',
                            type=str,
                            default='',
                            help='URL root for accessing Partner marketing site data.')
        parser.add_argument('--marketing-site-api-username',
                            action='store',
                            type=str,
                            default='',
                            help='Username used for accessing Partner marketing site data.')
        parser.add_argument('--marketing-site-api-password',
                            action='store',
                            type=str,
                            default='',
                            help='Password used for accessing Partner marketing site data.')

    def handle(self, *args, **options):
        """ Creates or updates Site and Partner records. """
        partner_code = options.get('partner_code')
        partner_name = options.get('partner_name')
        site_domain = options.get('site_domain')
        site_id = options.get('site_id')

        defaults = {'name': partner_name}
        if site_id:
            lookup = {'id': site_id}
            defaults['domain'] = site_domain
        else:
            lookup = {'domain': site_domain}

        site, __ = Site.objects.update_or_create(defaults=defaults, **lookup)

        __, created = Partner.objects.update_or_create(
            short_code=partner_code,
            defaults={
                'site': site,
                'name': partner_name,
                'courses_api_url': options.get('courses_api_url'),
                'lms_coursemode_api_url': options.get('lms_coursemode_api_url'),
                'ecommerce_api_url': options.get('ecommerce_api_url'),
                'organizations_api_url': options.get('organizations_api_url'),
                'programs_api_url': options.get('programs_api_url'),
                'lms_url': options.get('lms_url'),
                'studio_url': options.get('studio_url'),
                'marketing_site_api_url': options.get('marketing_site_api_url'),
                'marketing_site_url_root': options.get('marketing_site_url_root'),
                'marketing_site_api_username': options.get('marketing_site_api_username'),
                'marketing_site_api_password': options.get('marketing_site_api_password'),
                'publisher_url': options.get('publisher_url'),
            }
        )
        logger.info('Partner %s with code %s', 'created' if created else 'updated', partner_code)
