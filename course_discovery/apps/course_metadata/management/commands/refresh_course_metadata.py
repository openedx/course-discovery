import logging

from django.core.management import BaseCommand, CommandError
from edx_rest_api_client.client import EdxRestApiClient

from course_discovery.apps.core.models import Partner
from course_discovery.apps.course_metadata.data_loaders.api import (
    OrganizationsApiDataLoader, EcommerceApiDataLoader, ProgramsApiDataLoader, CoursesApiDataLoader,
)
from course_discovery.apps.course_metadata.data_loaders.marketing_site import (
    XSeriesMarketingSiteDataLoader, SubjectMarketingSiteDataLoader, SchoolMarketingSiteDataLoader,
    SponsorMarketingSiteDataLoader, PersonMarketingSiteDataLoader, CourseMarketingSiteDataLoader,
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

        parser.add_argument(
            '--partner_code',
            action='store',
            dest='partner_code',
            default=None,
            help='The short code for a specific partner to refresh.'
        )

        parser.add_argument(
            '-w', '--max_workers',
            type=int,
            action='store',
            dest='max_workers',
            default=7,
            help='Number of worker threads to use when traversing paginated responses.'
        )

    def handle(self, *args, **options):
        max_workers = options.get('max_workers')

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
                        '{root}/access_token'.format(root=partner.oidc_url_root.strip('/')),
                        partner.oidc_key,
                        partner.oidc_secret,
                        token_type=token_type
                    )
                except Exception:
                    logger.exception('No access token provided or acquired through client_credential flow.')
                    raise

            data_loaders = (
                (partner.marketing_site_url_root, SubjectMarketingSiteDataLoader,),
                (partner.marketing_site_url_root, SchoolMarketingSiteDataLoader,),
                (partner.marketing_site_url_root, SponsorMarketingSiteDataLoader,),
                (partner.marketing_site_url_root, PersonMarketingSiteDataLoader,),
                (partner.marketing_site_url_root, CourseMarketingSiteDataLoader,),
                (partner.organizations_api_url, OrganizationsApiDataLoader,),
                (partner.courses_api_url, CoursesApiDataLoader,),
                (partner.ecommerce_api_url, EcommerceApiDataLoader,),
                (partner.programs_api_url, ProgramsApiDataLoader,),
                (partner.marketing_site_url_root, XSeriesMarketingSiteDataLoader,),
            )

            for api_url, loader_class in data_loaders:
                if api_url:
                    try:
                        loader_class(partner, api_url, access_token, token_type, max_workers).ingest()
                    except Exception:  # pylint: disable=broad-except
                        logger.exception('%s failed!', loader_class.__name__)

            # TODO Cleanup CourseRun overrides equivalent to the Course values.
