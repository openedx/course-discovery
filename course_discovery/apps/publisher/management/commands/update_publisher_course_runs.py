import logging

from django.core.management import BaseCommand

from course_discovery.apps.publisher.dataloader.update_course_runs import get_and_update_course_runs

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Update course-runs into publisher app.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--start_id',
            action='store',
            dest='start_id',
            default=None,
            required=True,
            help='The Primary key value starting id to update the course-runs.'

        )

        parser.add_argument(
            '--end_id',
            action='store',
            dest='end_id',
            default=None,
            required=True,
            help='To this id course-runs will be updated.'
        )

    def handle(self, *args, **options):
        """ Import the course according to the given range."""
        start_id = options.get('start_id')
        end_id = options.get('end_id')

        get_and_update_course_runs(start_id, end_id)
