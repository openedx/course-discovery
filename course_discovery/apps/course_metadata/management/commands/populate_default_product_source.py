"""
Management command to populate the default identifier to the products having no identifier
"""
import logging

from django.conf import settings
from django.core.management import BaseCommand, CommandError
from django.db.transaction import atomic

from course_discovery.apps.course_metadata.models import Course, Program, Source

logger = logging.getLogger(__name__)


def get_products_with_no_product_source(product_type):
    """
    If product type is course then filtering the courses with no product_source and no additional_metadata because
    legacy edX courses do not have additional_metadata, only the courses from external sources have additional_metadata
    Else filtering the programs with no product_source and are not external degree programs
    """
    if product_type == 'course':
        return Course.everything.filter(product_source=None, additional_metadata=None)
    products = [
        program.id for program in Program.objects.filter(product_source=None)
        if not program.is_2u_degree_program
    ]
    return Program.objects.filter(id__in=products)


class Command(BaseCommand):
    help = 'Populate the default product_source to the products having no product_source'

    def add_arguments(self, parser):
        parser.add_argument(
            '--product_type',
            help='The product type we want to populate with default product source.'
                 'It can only be either course or program',
            default='course',
            required=False,
            type=str,
        )

    def handle(self, *args, **kwargs):
        product_type = kwargs.get('product_type', 'course').lower()
        try:
            if product_type not in ['course', 'program']:
                raise Exception(f"Product Type {product_type} is invalid")  # pylint: disable=broad-exception-raised
            default_product_source = Source.objects.get(slug=settings.DEFAULT_PRODUCT_SOURCE_SLUG)
            with atomic():
                products = get_products_with_no_product_source(product_type)
                # tranforming the queryset to list because after updating the products, the queryset becomes empty
                product_list = list(products)
                products.update(product_source=default_product_source)
                logger.info(f'Updated {len(product_list)} {product_type}s with default product_source')
                if len(product_list) > 0:
                    # pylint: disable=logging-not-lazy
                    if product_type == 'course':
                        logger.info('Updated courses:\n' +
                                    '\n'.join(f"{course.key} - {'draft' if course.draft else 'non-draft'}"
                                              for course in product_list))
                    else:
                        logger.info('Updated programs:\n' + '\n'.join(program.title for program in product_list))

        except Source.DoesNotExist as ex:
            logging.exception(f'Default product_source {settings.DEFAULT_PRODUCT_SOURCE_SLUG} does not exist')
            raise CommandError(f'Default product_source {settings.DEFAULT_PRODUCT_SOURCE_SLUG} does not exist') from ex
        except Exception as ex:
            logger.exception(f'Failed to update the courses with default product_source {ex}')
            raise CommandError(f'Failed to update the courses with default product_source {str(ex)}') from ex
