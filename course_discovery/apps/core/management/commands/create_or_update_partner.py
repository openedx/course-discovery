""" Creates or updates a Partner, including API and OIDC information """

import logging

from django.core.management import BaseCommand

from course_discovery.apps.core.models import Partner

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Create a new Partner, or update an existing Partner.'

    def add_arguments(self, parser):
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
                            dest='courses_api_url',
                            type=str,
                            default='',
                            help='API endpoint for accessing Partner course data.')
        parser.add_argument('--ecommerce-api-url',
                            action='store',
                            dest='ecommerce_api_url',
                            type=str,
                            default='',
                            help='API endpoint for accessing Partner ecommerce data.')
        parser.add_argument('--organizations-api-url',
                            action='store',
                            dest='organizations_api_url',
                            type=str,
                            default='',
                            help='API endpoint for accessing Partner organization data.')
        parser.add_argument('--programs-api-url',
                            action='store',
                            dest='programs_api_url',
                            type=str,
                            default='',
                            help='API endpoint for accessing Partner program data.')
        parser.add_argument('--marketing-site-api-url',
                            action='store',
                            dest='marketing_site_api_url',
                            type=str,
                            default='',
                            help='API endpoint for accessing Partner marketing site data.')
        parser.add_argument('--marketing-site-url-root',
                            action='store',
                            dest='marketing_site_url_root',
                            type=str,
                            default='',
                            help='URL root for accessing Partner marketing site data.')
        parser.add_argument('--marketing-site-api-username',
                            action='store',
                            dest='marketing_site_api_username',
                            type=str,
                            default='',
                            help='Username used for accessing Partner marketing site data.')
        parser.add_argument('--marketing-site-api-password',
                            action='store',
                            dest='marketing_site_api_password',
                            type=str,
                            default='',
                            help='Password used for accessing Partner marketing site data.')
        parser.add_argument('--oidc-url-root',
                            action='store',
                            dest='oidc_url_root',
                            type=str,
                            default='',
                            help='URL root used for Partner OIDC workflows.')
        parser.add_argument('--oidc-key',
                            action='store',
                            dest='oidc_key',
                            type=str,
                            default='',
                            help='Key used for Partner OIDC workflows.')
        parser.add_argument('--oidc-secret',
                            action='store',
                            dest='oidc_secret',
                            type=str,
                            default='',
                            help='Key used for Partner OIDC workflows.')

    def handle(self, *args, **options):
        """ Creates or updates a Partner record. """
        partner_code = options.get('partner_code')

        __, created = Partner.objects.update_or_create(
            short_code=partner_code,
            defaults={
                'name': options.get('partner_name'),
                'courses_api_url': options.get('courses_api_url'),
                'ecommerce_api_url': options.get('ecommerce_api_url'),
                'organizations_api_url': options.get('organizations_api_url'),
                'programs_api_url': options.get('programs_api_url'),
                'marketing_site_api_url': options.get('marketing_site_api_url'),
                'marketing_site_url_root': options.get('marketing_site_url_root'),
                'marketing_site_api_username': options.get('marketing_site_api_username'),
                'marketing_site_api_password': options.get('marketing_site_api_password'),
                'oidc_url_root': options.get('oidc_url_root'),
                'oidc_key': options.get('oidc_key'),
                'oidc_secret': options.get('oidc_secret'),
            }
        )
        logger.info('Partner %s with code %s', 'created' if created else 'updated', partner_code)
