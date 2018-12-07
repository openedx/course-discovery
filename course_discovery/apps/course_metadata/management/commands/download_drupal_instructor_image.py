import logging

import requests
from django.core.files.base import ContentFile
from django.core.management import BaseCommand

from course_discovery.apps.course_metadata.models import Person

logger = logging.getLogger(__name__)

IMAGE_TYPES = {
    'image/jpeg': 'jpg',
    'image/png': 'png',
}


class Command(BaseCommand):

    def add_arguments(self, parser):
        super().add_arguments(parser)

    def handle(self, *args, **options):
        # Get the Person objects that have the marketing URL Set
        persons = Person.objects.filter(
            profile_image_url__isnull=False
        ).exclude(
            profile_image_url='',
        )

        logger.info('There are {person_count} instructor images to download'.format(person_count=persons.count()))
        failed_image_pulls = []
        success_count = 0
        for person in persons:
            if person.profile_image and person.profile_image_url == person.profile_image.url:
                logger.info('image already local not retrieving image for Instructor {instructor} from {url}'.format(
                    instructor=person.full_name,
                    url=person.profile_image_url)
                )
                continue

            logger.info('retrieving image for Instructor {instructor} from {url}'.format(
                instructor=person.full_name,
                url=person.profile_image_url)
            )

            response = None
            # Try to Download the image
            try:
                # Set the User agent so that Download will get through
                headers = {
                    'User-Agent': 'edX Management Command Instructor Image Download',
                }
                response = requests.get(person.profile_image_url, headers=headers)
            except ConnectionError:
                logger.exception('Connection failure downloading image for {instructor} from {url}'.format(
                    instructor=person.full_name,
                    url=person.profile_image_url)
                )

            if response and response.status_code == requests.codes.ok:

                # Get the extension and check that it is in our list of image types
                content_type = response.headers['Content-Type'].lower()
                if content_type in IMAGE_TYPES:
                    extension = IMAGE_TYPES.get(content_type)
                    tmp_image_file = ContentFile(response.content, name='tmp.' + extension)
                    if tmp_image_file:
                        person.profile_image = tmp_image_file
                        person.save()
                        # Splitting these so that the URL updates using the correct file name
                        person.profile_image_url = person.profile_image.url
                        person.save()
                        success_count += 1
                        logger.info('Saved image for Instructor {instructor} from {url}'.format(
                            instructor=person.full_name,
                            url=person.profile_image_url)
                        )
                    else:
                        logger.error('failed to create image file for Instructor {instructor} from {url}'.format(
                            instructor=person.full_name,
                            url=person.profile_image_url)
                        )
                        failed_image_pulls.append(person.full_name)
                else:
                    logger.error('Unknown content type for instructor [{instructor}] and url [{url}]'.format(
                        instructor=person.full_name,
                        url=person.profile_image_url
                    ))
                    failed_image_pulls.append(person.full_name)
            else:
                logger.error('Failed to retrieve Image for {instructor} at {url} with status code [{status}]'.format(
                    instructor=person.full_name,
                    url=person.profile_image_url,
                    status=response.status_code
                ))
                failed_image_pulls.append(person.full_name)
        logger.info('----------------------------------------')
        logger.info('{count} Successfully Downloaded Images'.format(count=success_count))
        logger.info('{count} Failed Download attempts ---------'.format(count=len(failed_image_pulls)))
        for name in failed_image_pulls:
            logger.info(name)

