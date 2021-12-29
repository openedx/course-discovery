import logging

from django.core.management import BaseCommand

from course_discovery.apps.course_metadata.models import Course
from course_discovery.apps.course_metadata.utils import download_and_save_course_image

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Download course images to this server. This is intended to migrate image data from the edx.org ' \
           'marketing site to Discovery.'

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            '--overwrite',
            action='store_true',
            dest='overwrite_existing',
            help='Overwrite existing image content'
        )

    def handle(self, *args, **options):
        courses = Course.objects.filter(card_image_url__isnull=False).exclude(card_image_url='').order_by('key')

        if not options['overwrite_existing']:
            courses = courses.filter(image='')

        count = courses.count()
        if count < 1:
            logger.info('All courses are up to date.')
            return

        logger.info('Retrieving images for [%d] courses...', count)

        for course in courses:
            logger.info('Retrieving image for course [%s] from [%s]...', course.key, course.card_image_url)
            download_and_save_course_image(course, course.card_image_url)
