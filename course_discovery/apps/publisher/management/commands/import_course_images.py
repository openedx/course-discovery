import logging
from io import BytesIO

import requests
from django.core.files import File
from django.core.management import BaseCommand

from course_discovery.apps.publisher.models import Course

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
            try:
                self._download_image(course)
            except:  # pylint: disable=bare-except
                logger.error('Exception appear for course-id [%s].', course.id)

    def _download_image(self, course):

        # if image exists don't download it again.
        if course.image:
            return

        course_run = course.course_runs.first()
        if course_run and not course_run.card_image_url:
            return

        r = requests.get(course_run.card_image_url)

        if r.status_code == 200:
            image_data = File(BytesIO(r.content))
            course_run.course.image.save('image.jpg', content=image_data)
            course_run.course.save()
            logger.info('Successfully Import for course [%s]', course.id)
        else:
            logger.error('Loading the image for course-run [%s] failed.', course_run.id)
