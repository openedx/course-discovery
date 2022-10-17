"""
Data loader responsible for creating location restriction entries in discovery database,
"""
import csv
import logging
import uuid

import unicodecsv
from django_countries import countries

from course_discovery.apps.course_metadata.data_loaders import AbstractDataLoader
from course_discovery.apps.course_metadata.models import (
    AbstractLocationRestrictionModel, Course, CourseLocationRestriction, Program, ProgramLocationRestriction
)

logger = logging.getLogger(__name__)


class GeotargetingCSVDataLoader(AbstractDataLoader):
    """ Loads the geotargeting (location restriction) data from the csv file """
    # Below are the minimum required fields needed for successful data upload
    # Additional column names (for info purposes only) may be Product Name, Partner, Notes
    GEOTARGETING_REQUIRED_DATA_FIELDS = [
        'uuid', 'product_type', 'include_or_exclude',
    ]

    VALID_COUNTRY_CODES = [code for code, country in list(countries)]

    def __init__(self, partner, api_url=None, max_workers=None, is_threadsafe=False, csv_path=None, csv_file=None):
        super().__init__(partner, api_url, max_workers, is_threadsafe)
        self.skipped_items = []
        self.processed_courses = []
        self.processed_programs = []
        self.updated_course_location_restrictions = []
        try:
            # Read file from the path if given. Otherwise,
            # read from the file received from GeotargetingDataLoaderConfiguration.
            self.reader = csv.DictReader(open(csv_path, 'r')) if csv_path \
                else list(unicodecsv.DictReader(csv_file))  # lint-amnesty, pylint: disable=consider-using-with
        except FileNotFoundError:
            logger.exception("Error opening csv file at path {}".format(csv_path))    # lint-amnesty, pylint: disable=logging-format-interpolation
            raise  # re-raising exception to avoid moving the code flow

    def log_info(self, message, list_to_add):
        logger.info(message)
        list_to_add.append(message)

    def ingest(self):  # pylint: disable=too-many-statements
        logger.info("Initiating Geotargeting CSV data loader flow.")
        for row in self.reader:
            row = self.transform_dict_keys(row)
            row_uuid = row['uuid']
            product_type = row['product_type']

            message = self.validate_geotargeting_data(row)
            if message:
                logger.error(
                    'Data validation issue for product with UUID: {}.'  # lint-amnesty, pylint: disable=logging-format-interpolation
                    'Skipping ingestion for this item.'
                    'Details: {}'
                    .format(row_uuid, message)
                )
                self.skipped_items.append("Skipped {} with UUID {}. Errors: {}".format(product_type, row_uuid, message))
                continue

            logger.info('Starting data import flow for {}: {}'.format(product_type, row_uuid))  # lint-amnesty, pylint: disable=logging-format-interpolation

            restriction_type = None

            if row['include_or_exclude'] == 'include':
                restriction_type = AbstractLocationRestrictionModel.ALLOWLIST
            else:
                restriction_type = AbstractLocationRestrictionModel.BLOCKLIST

            loc_res = {
                'restriction_type': restriction_type,
                'countries': row['countries'] if row['countries'] else None
            }

            if product_type == 'course':
                # we need to find this course obj and then create or update related CourseLocationRestriction object
                for course_obj in Course.everything.filter(uuid=row_uuid):
                    action_taken = 'Created'
                    existing_loc_restriction_id = course_obj.location_restriction.id if course_obj.location_restriction else None  # lint-amnesty, pylint: disable=line-too-long
                    course_obj.location_restriction = CourseLocationRestriction.objects.create(**loc_res)
                    course_obj.save()
                    if existing_loc_restriction_id:
                        self.updated_course_location_restrictions.append(existing_loc_restriction_id)
                        action_taken = 'Updated'
                    self.log_info(
                        "{} geotargeting data for course with UUID: {}".format(action_taken, row_uuid),
                        self.processed_courses
                    )
            else:
                # we need to check if there already exists a ProgramLocationRestriction
                # for this program and update it if yes or create a new one if needed
                program_loc_restriction = ProgramLocationRestriction.objects.filter(program__uuid=row['uuid']).first()
                if program_loc_restriction:
                    # update existing
                    program_loc_restriction.restriction_type = loc_res['restriction_type']
                    program_loc_restriction.countries = loc_res['countries']
                    program_loc_restriction.save()
                    self.log_info(
                        "Updated geotargeting data for program with UUID: {}".format(row_uuid),
                        self.processed_programs
                    )
                else:
                    # create new
                    program_obj = Program.objects.filter(uuid=row['uuid']).first()
                    ProgramLocationRestriction.objects.create(
                        program=program_obj,
                        restriction_type=loc_res['restriction_type'],
                        countries=loc_res['countries']
                    )
                    self.log_info(
                        "Created geotargeting data for program with UUID: {}".format(row_uuid),
                        self.processed_programs
                    )

        # Check for potential orphans
        for loc_res_id in self.updated_course_location_restrictions:
            related_course = Course.everything.filter(location_restriction__id=loc_res_id).first()
            if not related_course:
                CourseLocationRestriction.objects.filter(id=loc_res_id).delete()
                logger.info("Removed orphaned course location restriction with id: {}".format(loc_res_id))  # lint-amnesty, pylint: disable=logging-format-interpolation

        logger.info("Geotargeting CSV loader ingest pipeline has completed.")

        # Log the summarized errors for all the skipped items for easy filtering for items whose ingestion failed
        if self.skipped_items:
            logger.info("Skipped items:")
            for msg in self.skipped_items:
                logger.error(msg)

        # log the processed course location restriction
        if self.processed_courses:
            logger.info("Successfully updated courses: ")
            for msg in self.processed_courses:
                logger.info(msg)

        # log the processed program location restriction
        if self.processed_programs:
            logger.info("Successfully updated programs: ")
            for msg in self.processed_programs:
                logger.info(msg)

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
            if updated_key == 'countries':
                transformed_dict[updated_key] = value.strip().upper().replace(";", ",") if value else ''
            else:
                transformed_dict[updated_key] = value.strip().lower()
        return transformed_dict

    def validate_geotargeting_data(self, data):
        """
        Verify the required data key-values
        As well as whether the values are correct
        and return a comma separated string of incorrect data fields
        """
        error_msgs = []

        # check if all required fields have been provided
        for field in self.GEOTARGETING_REQUIRED_DATA_FIELDS:
            if not (field in data and data[field]):
                error_msgs.append('Missing field: {}'.format(field))

        # check the values for each field
        is_valid_uuid = self.is_valid_uuid(data['uuid'])
        if not is_valid_uuid:
            error_msgs.append('Invalid UUID: {}'.format(data['uuid']))

        is_include_or_exclude = data['include_or_exclude'] == 'include' or data['include_or_exclude'] == 'exclude'
        if not is_include_or_exclude:
            error_msgs.append('Wrong include/exclude value for UUID: {}'.format(data['uuid']))

        is_course_or_program = data['product_type'] == 'course' or data['product_type'] == 'program'
        if not is_course_or_program:
            error_msgs.append('Wrong product_type value for UUID: {}'.format(data['uuid']))

        valid_countries_list = self.validate_countries_list(data)
        if not valid_countries_list:
            error_msgs.append('Error in the countries list for UUID: {}'.format(data['uuid']))

        if is_valid_uuid:  # only check if item exists if the provided uuid is valid
            item_found = self.validate_course_or_program(data)
            if not item_found:
                error_msgs.append('Course or Program with UUID {} was not found'.format(data['uuid']))

        if error_msgs:
            return ', '.join(error_msgs)
        return ''

    def is_valid_uuid(self, val):
        try:
            uuid.UUID(str(val))
            return True
        except ValueError:
            return False

    def validate_countries_list(self, data):
        """
        Verify if the countries list is empty or contains correct country codes
        Returns False is error was found
        """
        if not data['countries'] or data['countries'] == '':
            return True

        country_codes = data['countries'].upper().split(',')
        for country_code in country_codes:
            if country_code not in self.VALID_COUNTRY_CODES:
                return False
        return True

    def validate_course_or_program(self, data):
        """
        Verify if the given course or program exists
        Returns False if product could not be found
        """
        model = None
        if data['product_type'] == 'course':
            model = Course
        elif data['product_type'] == 'program':
            model = Program

        if not model:
            return False

        return self.validate_product_exists(model, 'uuid', data['uuid'])

    def validate_product_exists(self, model, key, value):
        """
        Get an object from the database by its key and value
        """
        model_name = model._meta.object_name
        kwrags = {key: value}
        try:
            return (
                model.everything.filter(**kwrags).exists() if model_name == 'Course'
                else model.objects.filter(**kwrags).exists()
            )
        except model.DoesNotExist:
            return False
