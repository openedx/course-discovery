import concurrent.futures
import itertools
import logging

from django.core.management import BaseCommand, CommandError
from edx_rest_api_client.client import EdxRestApiClient
import waffle

from course_discovery.apps.core.models import Partner
from course_discovery.apps.course_metadata.data_loaders.api import (
    OrganizationsApiDataLoader, EcommerceApiDataLoader, ProgramsApiDataLoader, CoursesApiDataLoader,
)
from course_discovery.apps.course_metadata.data_loaders.marketing_site import (
    XSeriesMarketingSiteDataLoader, SubjectMarketingSiteDataLoader, SchoolMarketingSiteDataLoader,
    SponsorMarketingSiteDataLoader, PersonMarketingSiteDataLoader, CourseMarketingSiteDataLoader,
)
from course_discovery.apps.course_metadata.models import Course


logger = logging.getLogger(__name__)


def execute_loader(loader_class, *loader_args):
    try:
        loader_class(*loader_args).ingest()
    except Exception:  # pylint: disable=broad-except
        logger.exception('%s failed!', loader_class.__name__)


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

            # If no courses exist for this partner, this command is likely being run on a
            # new catalog installation. In that case, we don't want multiple threads racing
            # to create courses. If courses do exist, this command is likely being run
            # as an update, significantly lowering the probability of race conditions.
            courses_exist = Course.objects.filter(partner=partner).exists()
            is_threadsafe = True if courses_exist and waffle.switch_is_active('threaded_metadata_write') else False

            logger.info(
                'Command is{negation} using threads to write data.'.format(negation='' if is_threadsafe else ' not')
            )

            pipeline = (
                (
                    (SubjectMarketingSiteDataLoader, partner.marketing_site_url_root, None),
                    (SchoolMarketingSiteDataLoader, partner.marketing_site_url_root, None),
                    (SponsorMarketingSiteDataLoader, partner.marketing_site_url_root, None),
                    (PersonMarketingSiteDataLoader, partner.marketing_site_url_root, None),
                ),
                (
                    (CourseMarketingSiteDataLoader, partner.marketing_site_url_root, None),
                    (OrganizationsApiDataLoader, partner.organizations_api_url, None),
                ),
                (
                    (CoursesApiDataLoader, partner.courses_api_url, None),
                ),
                (
                    (EcommerceApiDataLoader, partner.ecommerce_api_url, 1),
                    (ProgramsApiDataLoader, partner.programs_api_url, None),
                ),
                (
                    (XSeriesMarketingSiteDataLoader, partner.marketing_site_url_root, None),
                ),
            )

            if waffle.switch_is_active('parallel_refresh_pipeline'):
                for stage in pipeline:
                    with concurrent.futures.ProcessPoolExecutor() as executor:
                        for loader_class, api_url, max_workers_override in stage:
                            if api_url:
                                executor.submit(
                                    execute_loader,
                                    loader_class,
                                    partner,
                                    api_url,
                                    access_token,
                                    token_type,
                                    (max_workers_override or max_workers),
                                    is_threadsafe,
                                )
            else:
                # Flatten pipeline and run serially.
                for loader_class, api_url, max_workers_override in itertools.chain(*(stage for stage in pipeline)):
                    if api_url:
                        execute_loader(
                            loader_class,
                            partner,
                            api_url,
                            access_token,
                            token_type,
                            (max_workers_override or max_workers),
                            is_threadsafe,
                        )

            # TODO Cleanup CourseRun overrides equivalent to the Course values.
