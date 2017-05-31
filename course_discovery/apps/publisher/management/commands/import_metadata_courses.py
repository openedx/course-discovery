import logging

from django.core.management import BaseCommand

from course_discovery.apps.publisher.dataloader.create_courses import execute_query

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Import courses into publisher app.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--start_id',
            action='store',
            dest='start_id',
            default=None,
            required=True,
            help='The Primary key value starting id to import the courses.'

        )

        parser.add_argument(
            '--end_id',
            action='store',
            dest='end_id',
            default=None,
            required=True,
            help='To this id courses will be imported.'
        )

    def handle(self, *args, **options):
        """ Import the course according to the given range."""
        start_id = options.get('start_id')
        end_id = options.get('end_id')

        execute_query(start_id, end_id)
