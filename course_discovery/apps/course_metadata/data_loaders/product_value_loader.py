"""
Data loader responsible for creating product value entries in discovery database
"""
import csv
import logging
import uuid

import unicodecsv

from course_discovery.apps.course_metadata.data_loaders import AbstractDataLoader
from course_discovery.apps.course_metadata.models import Course, ProductValue, Program

logger = logging.getLogger(__name__)


class ProductValueCSVDataLoader(AbstractDataLoader):
    """Loads product value data from a csv file"""

    PRODUCT_VALUE_REQUIRED_DATA_FIELDS = [
        'uuid', 'product_type',
    ]

    PRODUCT_VALUE_DATA_FIELDS = [
        'per_click_usa', 'per_click_international', 'per_lead_usa', 'per_lead_international'
    ]

    def __init__(self, partner, api_url=None, max_workers=None, is_threadsafe=False, csv_path=None, csv_file=None):
        super().__init__(partner, api_url, max_workers, is_threadsafe)
        self.skipped_items = []
        self.processed_courses = []
        self.processed_programs = []
        self.updated_product_values = []
        try:
            self.reader = csv.DictReader(open(csv_path, 'r')) if csv_path \
                else list(unicodecsv.DictReader(csv_file))  # lint-amnesty, pylint: disable=consider-using-with

        except FileNotFoundError:
            logger.exception(f"Error opening csv file at path {csv_path}")
            raise

    def log_info(self, message, list_to_add):
        logger.info(message)
        list_to_add.append(message)

    def transform_dict_keys(self, data):
        """
        Given a data dictionary, return a new dict that has its keys transformed to
        snake case. For example, Enrollment Track becomes enrollment_track.

        Each key is stripped of whitespaces around the edges, converted to lower case,
        and has internal spaces converted to _. This convention removes the dependency on CSV
        headers format(Enrollment Track vs Enrollment track) and makes code flexible to ignore
        any case sensitivity, among other things.
        """
        transformed_dict = {}
        for key, value in data.items():
            updated_key = key.strip().lower().replace(' ', '_')
            transformed_dict[updated_key] = value.strip().lower()
        return transformed_dict

    def validate_required_fields(self, data, error_msgs):
        for field in self.PRODUCT_VALUE_REQUIRED_DATA_FIELDS:
            if not (field in data and data[field]):
                error_msgs.append(f'Missing required field: {field}')

    def validate_product_value_data(self, data):
        error_msgs = []

        self.validate_required_fields(data, error_msgs)
        self.validate_at_least_1_value_field(data, error_msgs)
        self.validate_uuid(data, error_msgs)
        self.validate_product_type(data, error_msgs)
        self.validate_product_exists(data, error_msgs)

        if error_msgs:
            return ', '.join(error_msgs)
        return ''

    def is_valid_uuid(self, val):
        try:
            uuid.UUID(str(val))
            return True
        except ValueError:
            return False

    def validate_uuid(self, data, error_msgs):
        is_valid_uuid = self.is_valid_uuid(data['uuid'])
        if not is_valid_uuid:
            error_msgs.append(f"Invalid UUID: {data['uuid']}")

    def validate_at_least_1_value_field(self, data, error_msgs):
        has_at_least_one_value_field = False

        for field in self.PRODUCT_VALUE_DATA_FIELDS:
            if (field in data and data[field]):
                has_at_least_one_value_field = True
                break

        if not has_at_least_one_value_field:
            error_msgs.append(f"Must have at least one optional field: {', '.join(self.PRODUCT_VALUE_DATA_FIELDS)}")

    def validate_product_type(self, data, error_msgs):
        is_course_or_program = data['product_type'] == 'course' or data['product_type'] == 'program'
        if not is_course_or_program:
            error_msgs.append(f"Wrong product_type value for UUID: {data['uuid']}")

    def validate_product_exists(self, data, error_msgs):
        """
        Get an object from the database by its key and value
        """
        if not self.is_valid_uuid(data['uuid']):
            # invalid uuid captured in another validator
            error_msgs.append("Unable to validate that product exists due to invalid UUID")
            return

        models = {'course': Course, 'program': Program}
        try:
            model = models[data['product_type']]
        except KeyError:
            # invalid product_type error_msg captured in another validator
            error_msgs.append("Unable to validate that product exists due to invalid Product Type")
            return

        model_name = model._meta.object_name
        kwrags = {'uuid': data['uuid']}
        exists = False

        if model_name == 'Course':
            exists = model.everything.filter(**kwrags).exists()
        else:
            exists = model.objects.filter(**kwrags).exists()

        if not exists:
            error_msgs.append(f"{data['product_type'].capitalize()} with UUID: {data['uuid']} was not found")

    def generate_values_dict(self, data, product_value=None):
        values = {}
        if product_value is None:
            product_value = {}
        for field in self.PRODUCT_VALUE_DATA_FIELDS:
            if (field in data and data[field]):
                values[field] = data[field]
            elif hasattr(product_value, field):
                values[field] = getattr(product_value, field)
            else:
                values[field] = 0
        return values

    def process_course(self, data):
        for course_obj in Course.everything.filter(uuid=data['uuid']):
            action_taken = 'Created'
            product_value_obj = course_obj.in_year_value if course_obj.in_year_value else None
            product_value_data = self.generate_values_dict(data, product_value_obj)
            course_obj.in_year_value = ProductValue.objects.create(**product_value_data)
            course_obj.save()
            if product_value_obj:
                self.updated_product_values.append(product_value_obj)
                action_taken = 'Updated'
            self.log_info(
                f"{action_taken} product value data for course with UUID: {data['uuid']}",
                self.processed_courses
            )

    def process_program(self, data):
        program_obj = Program.objects.filter(uuid=data['uuid']).first()
        action_taken = "Updated"
        if program_obj.in_year_value:
            self.updated_product_values.append(program_obj.in_year_value)
            product_value_data = self.generate_values_dict(data, program_obj.in_year_value)
            program_obj.in_year_value = ProductValue.objects.create(**product_value_data)
            program_obj.save()

        else:
            product_value_data = self.generate_values_dict(data)
            program_obj.in_year_value = ProductValue.objects.create(**product_value_data)
            program_obj.save()
            action_taken = "Created"

        self.log_info(
            f"{action_taken} product value data for program with UUID: {data['uuid']}",
            self.processed_programs
        )

    def check_for_orphaned_product_values(self):
        for product_value in self.updated_product_values:
            related_course = Course.everything.filter(in_year_value=product_value).first()
            related_program = Program.objects.filter(in_year_value=product_value).first()
            if (related_course is None and related_program is None):
                ProductValue.objects.filter(id=product_value.id).delete()
                logger.info(f"Removed orphaned product value with id: {product_value.id}")

    def ingest(self):
        logger.info("Initiating Product Value CSV data loader flow.")
        for row in self.reader:
            row = self.transform_dict_keys(row)
            row_uuid = row['uuid']
            product_type = row['product_type']

            message = self.validate_product_value_data(row)
            if message:
                logger.error(
                    f'Data validation issue for product with UUID: {row_uuid}.'
                    f' Skipping ingestion for this item. Details: {message}'
                )
                self.skipped_items.append(f"Skipped {product_type} with UUID {row_uuid}. Errors: {message}")
                continue

            logger.info(f'Starting data import flow for {product_type}: {row_uuid}')

            if product_type == 'course':
                self.process_course(row)
            else:
                self.process_program(row)

        logger.info("Product Value CSV loader ingest pipeline has completed.")

        logger.info("Checking for orphaned product value records.")

        self.check_for_orphaned_product_values()

        if self.skipped_items:
            logger.info("Skipped items:")
            for msg in self.skipped_items:
                logger.error(msg)

        if self.processed_courses:
            logger.info("Successfully updated courses:")
            for msg in self.processed_courses:
                logger.info(msg)

        if self.processed_programs:
            logger.info("Successfully updated programs:")
            for msg in self.processed_programs:
                logger.info(msg)

        logger.info("Product Value ingestion complete!")
