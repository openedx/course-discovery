import concurrent.futures
import itertools
import logging

from django.core.management import BaseCommand, CommandError
from django.db import connection
from edx_rest_api_client.client import EdxRestApiClient
import jwt
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


def execute_loader(loader_class, *loader_args, **loader_kwargs):
    try:
        loader_class(*loader_args, **loader_kwargs).ingest()
    except Exception:  # pylint: disable=broad-except
        logger.exception('%s failed!', loader_class.__name__)


def execute_parallel_loader(loader_class, *loader_args):
    """
    ProcessPoolExecutor uses the multiprocessing module. Multiprocessing forks processes,
    causing connection objects to be copied across processes. The key goal when running
    multiple Python processes is to prevent any database connections from being shared
    across processes. Depending on specifics of the driver and OS, the issues that arise
    here range from non-working connections to socket connections that are used by multiple
    processes concurrently, leading to broken messaging (e.g., 'MySQL server has gone away').

    To get around this, we force each process to open its own connection to the database by
    closing the existing, copied connection as soon as we're within the new process. This works
    because as long as there is no existing, open connection, Django is smart enough to initialize
    a new connection the next time one is necessary.
    """
    connection.close()

    execute_loader(loader_class, *loader_args)


class Command(BaseCommand):
    help = 'Refresh course metadata from external sources.'

    def add_arguments(self, parser):
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

        token_type = 'JWT'
        for partner in partners:
            logger.info('Retrieving access token for partner [{}]'.format(partner_code))

            try:
                access_token, __ = EdxRestApiClient.get_oauth_access_token(
                    '{root}/access_token'.format(root=partner.oidc_url_root.strip('/')),
                    partner.oidc_key,
                    partner.oidc_secret,
                    token_type=token_type
                )
            except Exception:
                logger.exception('No access token acquired through client_credential flow.')
                raise
            username = jwt.decode(access_token, verify=False)['preferred_username']
            kwargs = {'username': username} if username else {}

            # The Linux kernel implements copy-on-write when fork() is called to create a new
            # process. Pages that the parent and child processes share, such as the database
            # connection, are marked read-only. If a write is performed on a read-only page
            # (e.g., closing the connection), it is then copied, since the memory is no longer
            # identical between the two processes. This leads to the following behavior:
            #
            # 1) Newly forked process
            #       parent
            #              -> connection (Django open, MySQL open)
            #       child
            #
            # 2) Child process closes the connection
            #       parent -> connection (*Django open, MySQL closed*)
            #       child  -> connection (Django closed, MySQL closed)
            #
            # Calling connection.close() from a child process causes the MySQL server to
            # close a connection which the parent process thinks is still usable. Since
            # the parent process thinks the connection is still open, Django won't attempt
            # to open a new one, and the parent ends up running a query on a closed connection.
            # This results in a 'MySQL server has gone away' error.
            #
            # To resolve this, we force Django to reconnect to the database before running any queries.
            connection.connect()

            # If no courses exist for this partner, this command is likely being run on a
            # new catalog installation. In that case, we don't want multiple threads racing
            # to create courses. If courses do exist, this command is likely being run
            # as an update, significantly lowering the probability of race conditions.
            courses_exist = Course.objects.filter(partner=partner).exists()
            is_threadsafe = courses_exist and waffle.switch_is_active('threaded_metadata_write')

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
                                    execute_parallel_loader,
                                    loader_class,
                                    partner,
                                    api_url,
                                    access_token,
                                    token_type,
                                    (max_workers_override or max_workers),
                                    is_threadsafe,
                                    **kwargs,
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
                            **kwargs,
                        )

            # TODO Cleanup CourseRun overrides equivalent to the Course values.
