import logging

from django.conf import settings
from django.core.management import BaseCommand, CommandError
from edx_rest_api_client.client import EdxRestApiClient

from course_discovery.apps.course_metadata.data_loaders import (
    CoursesApiDataLoader, DrupalApiDataLoader, OrganizationsApiDataLoader, EcommerceApiDataLoader, ProgramsApiDataLoader
)

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

    def handle(self, *args, **options):
        access_token = options.get('access_token')
        token_type = options.get('token_type')

        if access_token and not token_type:
            raise CommandError('The token_type must be specified when passing in an access token!')

        if not access_token:
            logger.info('No access token provided. Retrieving access token using client_credential flow...')
            token_type = 'JWT'

            try:
                access_token, __ = EdxRestApiClient.get_oauth_access_token(
                    '{root}/access_token'.format(root=settings.SOCIAL_AUTH_EDX_OIDC_URL_ROOT),
                    settings.SOCIAL_AUTH_EDX_OIDC_KEY,
                    settings.SOCIAL_AUTH_EDX_OIDC_SECRET,
                    token_type=token_type
                )
            except Exception:
                logger.exception('No access token provided or acquired through client_credential flow.')
                raise

        loaders = (
            (OrganizationsApiDataLoader, settings.ORGANIZATIONS_API_URL,),
            (CoursesApiDataLoader, settings.COURSES_API_URL,),
            (EcommerceApiDataLoader, settings.ECOMMERCE_API_URL,),
            (DrupalApiDataLoader, settings.MARKETING_API_URL,),
            (ProgramsApiDataLoader, settings.PROGRAMS_API_URL,),
        )

        for loader_class, api_url in loaders:
            try:
                loader_class(api_url, access_token, token_type).ingest()
            except Exception:
                logger.exception('%s failed!', loader_class.__name__)
