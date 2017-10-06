import logging

import requests
from django.core.files.base import ContentFile
from django.core.management import BaseCommand

from course_discovery.apps.course_metadata.models import Course

logger = logging.getLogger(__name__)

IMAGE_TYPES = {
    'image/jpeg': 'jpg',
    'image/png': 'png',
}


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

            try:
                response = requests.get(course.card_image_url)

                if response.status_code == requests.codes.ok:  # pylint: disable=no-member
                    content_type = response.headers['Content-Type'].lower()
                    extension = IMAGE_TYPES.get(content_type)

                    if extension:
                        filename = '{uuid}.{extension}'.format(uuid=str(course.uuid), extension=extension)
                        course.image.save(filename, ContentFile(response.content))
                        logger.info('Image for course [%s] successfully updated.', course.key)
                    else:
                        # pylint: disable=line-too-long
                        msg = 'Image retrieved for course [%s] from [%s] has an unknown content type [%s] and will not be saved.'
                        logger.error(msg, course.key, course.card_image_url, content_type)

                else:
                    msg = 'Failed to download image for course [%s] from [%s]! Response was [%d]:\n%s'
                    logger.error(msg, course.key, course.card_image_url, response.status_code, response.content)
            except Exception:  # pylint: disable=broad-except
                logger.exception('An unknown exception occurred while downloading image for course [%s]', course.key)
