import logging
from optparse import make_option

from django.core.management import BaseCommand, CommandError

from course_discovery.apps.courses.models import Course

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Refresh course data from external sources.'

    option_list = BaseCommand.option_list + (
        make_option('--access_token',
                    action='store',
                    dest='access_token',
                    default=None,
                    help='OAuth2 access token used to authenticate API calls.'),
    )

    def handle(self, *args, **options):
        access_token = options.get('access_token')

        if not access_token:
            msg = 'Courses cannot be migrated if no access token is supplied.'
            logger.error(msg)
            raise CommandError(msg)

        Course.refresh_all(access_token=access_token)
