import logging

from django.core.exceptions import ValidationError
from django.core.management import BaseCommand

from course_discovery.apps.course_metadata.models import BulkUpdateImagesConfig, Image

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """ Management command to bulk update Image objects. Uses config BulkUpdateImagesConfig
    to be filled with the correct mapping of old url to new url, entered as a new line separated list of
    <old_url> <new_url>
    ./manage.py update_images """

    help = 'Modify Image objects in bulk with arguments from database'

    def handle(self, *args, **options):
        config = BulkUpdateImagesConfig.get_solo()
        lines = config.image_urls.split('\n')
        for line in lines:
            tokenized = line.strip().split(' ', 1)
            if len(tokenized) != 2:
                logger.warning('Incorrectly formatted line %s', line)
                continue
            try:
                image = Image.objects.filter(src=tokenized[0]).first()
                if not image:
                    logger.warning('Cannot find image with url "{url}"'.format(url=tokenized[0]))  # lint-amnesty, pylint: disable=logging-format-interpolation
                    continue
                image.src = tokenized[1]
                image.full_clean()
                image.save()
            except ValidationError:
                logger.warning('Invalid image url: "{url}"'.format(url=tokenized[1]))  # lint-amnesty, pylint: disable=logging-format-interpolation
                continue
