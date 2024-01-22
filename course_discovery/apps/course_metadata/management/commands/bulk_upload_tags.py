"""
Management command to add tags to courses
"""
import logging
import uuid

from django.core.management import BaseCommand, CommandError

from course_discovery.apps.course_metadata.models import BulkUploadTagsConfig, Course, Program

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Add SEO tags to products parsed from a CSV file'

    # Mapping of SEO tags field names to the corresponding product type
    PRODUCT_TYPE_TO_TAGS_FIELD_MAPPING = {
        'course': {'model': Course, 'field': 'topics'},
        'program': {'model': Program, 'field': 'labels'},
        'degree': {'model': Program, 'field': 'labels'},
    }
    PRODUCT_TYPES = ['course', 'program', 'degree']

    def add_arguments(self, parser):
        parser.add_argument(
            '--csv_path',
            help='Path to the CSV file',
            type=str,
        )

    def handle(self, *args, **options):
        csv_path = options.get('csv_path', None)
        bulk_upload_tags_config = BulkUploadTagsConfig.current()

        try:
            if csv_path:
                file_handle = open(csv_path, "r")  # pylint: disable=consider-using-with
            else:
                file_handle = bulk_upload_tags_config.csv_file if bulk_upload_tags_config.is_enabled() else None
                file_handle.open('r')
        except Exception as exc:
            raise CommandError(  # pylint: disable=raise-missing-from
                "Error occured while opening the tags csv.\n{}".format(exc)
            )

        for row in file_handle:
            if row:
                product_uuid, product_type, tags = self.parse_row(row)
                if product_type not in self.PRODUCT_TYPES:
                    logger.info(f'Invalid product type: {product_type}')
                    continue
                self.set_product_tags(product_uuid, tags, product_type)

        file_handle.close()

    def parse_row(self, row):
        """
        Parse a line from the csv file and return the product uuid and list of tags
        uuid,tag1,tag2,tag3 -> uuid, [tag1, tag2, tag3]
        """
        product_uuid, product_type, *tags = row.split(',')
        return product_uuid.strip().lower(), product_type.strip(), [tag.strip() for tag in tags]

    def set_product_tags(self, product_uuid, tags, product_type):
        """
        Set the tags for a product of the given type and UUID.

        Args:
            product_uuid (str): The UUID of the product to set tags for.
            tags (List[str]): A list of tags to set for the product. Empty strings are ignored.
            product_type (str): The type of product to set tags for. Must be one of 'course', 'program', or 'degree'.

        Example usage:

        ```
        set_product_tags('dummy-uuid', ['tag1', 'tag2'], 'course')
        ```
        """
        if not self.is_valid_uuid(product_uuid):
            logger.info(f'Invalid uuid: {product_uuid}')
            return
        tags = [tag for tag in tags if tag]

        mapping = self.PRODUCT_TYPE_TO_TAGS_FIELD_MAPPING.get(product_type)
        if not mapping:
            logger.info(f'Invalid product type: {product_type}')
            return

        model = mapping['model']
        field = mapping['field']

        if model == Course:
            query_set = Course.everything.filter(uuid=product_uuid)
        else:
            query_set = model.objects.filter(uuid=product_uuid)
        if not query_set:
            logger.info(f'No {product_type} found with uuid: {product_uuid}')
            return

        for obj in query_set:
            logger.info(f'Setting tags for {product_type} with uuid -{product_uuid}: {tags}')
            getattr(obj, field).set(tags)
            obj.save()

    def is_valid_uuid(self, product_uuid):
        """ Check if the product uuid is valid """
        try:
            uuid.UUID(str(product_uuid))
            return True
        except ValueError:
            return False
