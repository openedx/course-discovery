import logging

from django.core.management import BaseCommand

from course_discovery.apps.course_metadata.models import Course as DiscoveryCourse
from course_discovery.apps.publisher.models import Course as PublisherCourse

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Re-publish the course images we have on publisher to discovery course objects'

    def add_arguments(self, parser):
        parser.add_argument(
            '--start_id',
            action='store',
            dest='start_id',
            required=True,
            help='The Publisher course Primary key value starting id to re-publish the course image.'

        )

        parser.add_argument(
            '--end_id',
            action='store',
            dest='end_id',
            required=True,
            help='To this id of the Publisher Course the course image will be re-published.'
        )

    def handle(self, *args, **options):
        start_id = options.get('start_id')
        end_id = options.get('end_id')

        publisher_courses = PublisherCourse.objects.filter(id__range=(start_id, end_id), image__isnull=False)
        for publisher_course in publisher_courses:
            discovery_course = None
            try:
                discovery_course = publisher_course.discovery_counterpart
            except DiscoveryCourse.DoesNotExist:
                logger.warning('Publisher course {} has no discovery counterpart!'.format(publisher_course.number))

            if discovery_course:
                logger.info('Re-render course image for course [{}]'.format(publisher_course.key))
                discovery_course.image.save(publisher_course.image.name, publisher_course.image.file)
