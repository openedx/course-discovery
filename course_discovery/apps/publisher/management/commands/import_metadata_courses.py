import logging

from django.core.management import BaseCommand

from course_discovery.apps.course_metadata.models import Course
from course_discovery.apps.publisher.dataloader.create_courses import process_course

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
        """ Import the course according to the given range. But in prod for multiple runs there are multiple
        courses. During import just pick the latest course and do not import the old ones.
        """
        start_id = options.get('start_id')
        end_id = options.get('end_id')

        for course in Course.objects.filter(id__range=(start_id, end_id)):
            process_course(course)
