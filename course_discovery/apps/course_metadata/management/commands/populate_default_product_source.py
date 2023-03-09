"""
Management command to populate the default identifier to the courses having no identifier
"""
import logging

from django.conf import settings
from django.core.management import BaseCommand, CommandError
from django.db.transaction import atomic

from course_discovery.apps.course_metadata.models import Course, Source

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Populate the default product_source to the courses having no product_source'

    def handle(self, *args, **kwargs):
        try:
            default_product_source = Source.objects.get(slug=settings.DEFAULT_PRODUCT_SOURCE_SLUG)
            with atomic():
                # filtering the courses with no product_source and no additional_metadata because legacy edX courses
                # do not have additional_metadata, only the courses from external sources have additional_metadata
                courses = Course.everything.filter(product_source=None, additional_metadata=None)
                # tranforming the queryset to list because after updating the courses, the queryset becomes empty
                courses_list = list(courses)
                courses.update(product_source=default_product_source)
                logger.info(f'Updated {len(courses_list)} courses with default product_source')
                if len(courses_list) > 0:
                    # pylint: disable=logging-not-lazy
                    logger.info('Updated courses:\n' +
                                '\n'.join(f"{course.key} - {'draft' if course.draft else 'non-draft'}"
                                          for course in courses_list))

        except Source.DoesNotExist as ex:
            logging.exception(f'Default product_source {settings.DEFAULT_PRODUCT_SOURCE_SLUG} does not exist')
            raise CommandError(f'Default product_source {settings.DEFAULT_PRODUCT_SOURCE_SLUG} does not exist') from ex
        except Exception as ex:
            logger.exception(f'Failed to update the courses with default product_source {ex}')
            raise CommandError(f'Failed to update the courses with default product_source {str(ex)}') from ex
