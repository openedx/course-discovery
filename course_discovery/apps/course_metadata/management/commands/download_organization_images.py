import logging

import requests
from django.core.files.base import ContentFile
from django.core.management import BaseCommand

from course_discovery.apps.course_metadata.models import Organization

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Download organization images from the url properties.'

    def download_and_set_image(self, org, value, field):
        image_field = field[:-4]
        org_uuid = org.uuid
        try:
            logo = requests.get('{}'.format(value))
        except Exception:  # pylint: disable=broad-except
            logger.error('Could not get [%s] for organization [%s]', image_field, org_uuid)
        else:
            try:
                image = getattr(org, field[:-4])
                image.save(value.split('/')[-1], ContentFile(logo.content))
                logger.info('Successfully downloaded [%s] for organization [%s]', image_field, org_uuid)
            except Exception:  # pylint: disable=broad-except
                logger.error('Could not set [%s] for organization [%s]', image_field, org_uuid)

    def handle(self, *args, **options):
        organizations = Organization.objects.all()
        url_fields = ('logo_image_url', 'banner_image_url', 'certificate_logo_image_url',)
        for org in organizations:
            for field in url_fields:
                value = getattr(org, field)
                if value:
                    self.download_and_set_image(org, value, field)
        logger.info('Download of Organization images complete!')
