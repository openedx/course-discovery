import logging

from django.core.management import BaseCommand, CommandError
from edx_rest_api_client.client import EdxRestApiClient

from course_discovery.apps.course_metadata.data_loaders import (
    CoursesApiDataLoader, DrupalApiDataLoader, OrganizationsApiDataLoader, EcommerceApiDataLoader, ProgramsApiDataLoader
)
from course_discovery.apps.core.models import Partner

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Refresh course metadata from external sources.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--access_token',
            action='store',
            dest='access_token',
            default=None,
            help='OAuth2 access token used to authenticate API calls.'
        )

        parser.add_argument(
            '--token_type',
            action='store',
            dest='token_type',
            default=None,
            help='The type of access token being passed  (e.g. Bearer, JWT).'
        )

        parser.add_argument(
            '--partner_code',
            action='store',
            dest='partner_code',
            default=None,
            help='The short code for a specific partner to refresh.'
        )

    def handle(self, *args, **options):
        # For each partner defined...
        partners = Partner.objects.all()

        # If a specific partner was indicated, filter down the set
        partner_code = options.get('partner_code')
        if partner_code:
            partners = partners.filter(short_code=partner_code)

        if not partners:
            raise CommandError('No partners available!')

        for partner in partners:

            access_token = options.get('access_token')
            token_type = options.get('token_type')

            if access_token and not token_type:
                raise CommandError('The token_type must be specified when passing in an access token!')

            if not access_token:
                logger.info('No access token provided. Retrieving access token using client_credential flow...')
                token_type = 'JWT'

                try:
                    access_token, __ = EdxRestApiClient.get_oauth_access_token(
                        '{root}/access_token'.format(root=partner.social_auth_edx_oidc_url_root.strip('/')),
                        partner.social_auth_edx_oidc_key,
                        partner.social_auth_edx_oidc_secret,
                        token_type=token_type
                    )
                except Exception:
                    logger.exception('No access token provided or acquired through client_credential flow.')
                    raise

            loaders = []

            if partner.organizations_api_url:
                loaders.append(OrganizationsApiDataLoader)
            if partner.courses_api_url:
                loaders.append(CoursesApiDataLoader)
            if partner.ecommerce_api_url:
                loaders.append(EcommerceApiDataLoader)
            if partner.marketing_api_url:
                loaders.append(DrupalApiDataLoader)
            if partner.programs_api_url:
                loaders.append(ProgramsApiDataLoader)

            if loaders:
                for loader_class in loaders:
                    try:
                        loader_class(
                            partner,
                            access_token,
                            token_type,
                        ).ingest()
                    except Exception:  # pylint: disable=broad-except
                        logger.exception('%s failed!', loader_class.__name__)
