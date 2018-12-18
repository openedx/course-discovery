import logging
import requests

from django.core.files.base import ContentFile
from django.core.management import BaseCommand

from course_discovery.apps.course_metadata.models import Person, ProfileImageDownloadConfig

logger = logging.getLogger(__name__)

IMAGE_TYPES = {
    'image/jpeg': 'jpg',
    'image/png': 'png',
    'image/gif': 'gif',
}


class Command(BaseCommand):

    def handle(self, *args, **options):
        config = ProfileImageDownloadConfig.get_solo()
        person_uuids = [uuid_str.strip() for uuid_str in config.person_uuids.split(',')]

        # Get the Person objects that have the marketing URL Set
        persons = Person.objects.filter(
            uuid__in=person_uuids
        )

        logger.info('There are {person_count} instructor images to download'.format(person_count=persons.count()))
        failed_image_pulls = []
        success_count = 0
        for person in persons:
            if not person.profile_image_url:
                logger.info(
                    'No Drupal profile_image_url for {instructor}, [{uuid}], no download required'.format(
                        uuid=person.uuid,
                        instructor=person.full_name,
                    ))
                continue
            if person.profile_image and person.profile_image_url == person.profile_image.url:
                logger.info(
                    'image already local not retrieving image for Instructor {instructor}, [{uuid}], from {url}'.format(
                        uuid=person.uuid,
                        instructor=person.full_name,
                        url=person.profile_image_url
                    ))
                continue

            logger.info('retrieving image for Instructor {instructor}, [{uuid}], from {url}'.format(
                instructor=person.full_name,
                uuid=person.uuid,
                url=person.profile_image_url)
            )

            # Try to Download the image
            try:
                # Set the User agent so that Download will get through
                headers = {
                    'User-Agent': 'edX Management Command Instructor Image Download',
                }
                response = requests.get(person.profile_image_url, headers=headers)
            except requests.exceptions.ConnectionError:
                logger.exception('Connection failure downloading image for {instructor}, [{uuid}], from {url}'.format(
                    instructor=person.full_name,
                    uuid=person.uuid,
                    url=person.profile_image_url)
                )
                continue

            if response and response.status_code == requests.codes.ok:  # pylint: disable=no-member

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
                        logger.info('Saved image for Instructor {instructor}, [{uuid}], from {url}'.format(
                            instructor=person.full_name,
                            uuid=person.uuid,
                            url=person.profile_image_url)
                        )
                    else:
                        logger.error(
                            'failed to create image file for Instructor {instructor}, [{uuid}], from {url}'.format(
                                instructor=person.full_name,
                                uuid=person.uuid,
                                url=person.profile_image_url
                            )
                        )
                        failed_image_pulls.append(str(person.uuid))
                else:
                    logger.error('Unknown content type for instructor [{instructor}], [{uuid}], and url [{url}]'.format(
                        instructor=person.full_name,
                        uuid=person.uuid,
                        url=person.profile_image_url
                    ))
                    failed_image_pulls.append(person.full_name)
            else:
                logger.error(
                    'Failed to retrieve Image for {instructor}, [{uuid}], at {url} with status code [{status}]'.format(
                        instructor=person.full_name,
                        uuid=person.uuid,
                        url=person.profile_image_url,
                        status=response.status_code
                    ))
                failed_image_pulls.append(person.full_name)
        logger.info('----------------------------------------')
        logger.info('{count} Successfully Downloaded Images'.format(count=success_count))
        logger.info('{count} Failed Download attempts ---------'.format(count=len(failed_image_pulls)))
        for uuid in failed_image_pulls:
            logger.info(uuid)
