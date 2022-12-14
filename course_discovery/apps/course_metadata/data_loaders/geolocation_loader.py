"""
Data loader responsible for creating location restriction entries in discovery database,
"""
import csv
import logging
import uuid

import unicodecsv

from course_discovery.apps.course_metadata.data_loaders import AbstractDataLoader
from course_discovery.apps.course_metadata.models import Course, GeoLocation, Program

logger = logging.getLogger(__name__)


class GeolocationCSVDataLoader(AbstractDataLoader):
    """ Loads the geolocation (lat/lng) data from the csv file """
    # Below are the minimum required fields needed for successful data upload
    # Additional column names (for info purposes only) may be Product Name, Partner, Notes
    GEOLOCATION_REQUIRED_DATA_FIELDS = [
        'uuid', 'product_type', 'location_name', 'latitude', 'longtitude',
    ]

    def __init__(self, partner, api_url=None, max_workers=None, is_threadsafe=False, csv_path=None, csv_file=None):
        super().__init__(partner, api_url, max_workers, is_threadsafe)
        self.skipped_items = []
        self.processed_courses = []
        self.processed_programs = []
        self.updated_geolocations = []
        try:
            # Read file from the path if given. Otherwise,
            # read from the file received from GeolocationDataLoaderConfiguration.
            self.reader = csv.DictReader(open(csv_path, 'r')) if csv_path \
                else list(unicodecsv.DictReader(csv_file))  # lint-amnesty, pylint: disable=consider-using-with
        except FileNotFoundError:
            logger.exception("Error opening csv file at path {}".format(csv_path))    # lint-amnesty, pylint: disable=logging-format-interpolation
            raise  # re-raising exception to avoid moving the code flow

    def log_info(self, message, list_to_add):
        logger.info(message)
        list_to_add.append(message)

    def ingest(self):
        logger.info("Initiating Geolocation CSV data loader flow.")
        processed_products = {
            'course': self.processed_courses,
            'program': self.processed_programs,
        }

        for row in self.reader:
            row = self.transform_dict_keys(row)
            row_uuid = row['uuid']
            product_type = row['product_type']
            model = Course if product_type == 'course' else Program

            geolocation = {
                'location_name': row['location_name'],
                'lat': row['latitude'],
                'lng': row['longtitude'],
            }

            err_message = self.validate_geolocation_data(row)
            if err_message:
                logger.error(
                    'Data validation issue for product with UUID: {}.'  # lint-amnesty, pylint: disable=logging-format-interpolation
                    'Skipping ingestion for this item.'
                    'Details: {}'
                    .format(row_uuid, err_message)
                )
                self.skipped_items.append("Skipped {} with UUID {}. Errors: {}".format(product_type, row_uuid, err_message))  # pylint: disable=line-too-long
                continue

            logger.info('Starting data import flow for {}: {}'.format(product_type, row_uuid))  # lint-amnesty, pylint: disable=logging-format-interpolation

            self.ingest_entry(model, row_uuid, geolocation, processed_products[product_type])

        self.check_for_potential_orphans_in_courses()

        logger.info("Geolocation CSV loader ingest pipeline has completed.")

        self.log_skipped_items()

        self.log_processed_products()

    def ingest_entry(self, model, row_uuid, geolocation, processed_products):
        products = model.everything.filter(uuid=row_uuid) if model is Course else model.objects.filter(uuid=row_uuid)

        for product_obj in products:
            action_taken = 'Created'
            existing_geolocation_id = product_obj.geolocation.id if product_obj.geolocation else None  # lint-amnesty

            product_obj.geolocation = GeoLocation.objects.create(**geolocation)
            product_obj.save()

            if existing_geolocation_id:
                self.updated_geolocations.append(existing_geolocation_id)
                action_taken = 'Updated'

            self.log_info(
                "{} geolocation data for product with UUID: {}".format(action_taken, row_uuid),
                processed_products
            )

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

    def validate_geolocation_data(self, data):
        """
        Verify the required data key-values
        As well as whether the values are correct
        and return a comma separated string of incorrect data fields
        """
        error_msgs = []

        # check if all required fields have been provided
        for field in self.GEOLOCATION_REQUIRED_DATA_FIELDS:
            if not (field in data and data[field]):
                error_msgs.append('Missing field: {}'.format(field))

        # check the values for each field
        is_valid_uuid = self.is_valid_uuid(data['uuid'])
        if not is_valid_uuid:
            error_msgs.append('Invalid UUID: {}'.format(data['uuid']))

        is_course_or_program = data['product_type'] == 'course' or data['product_type'] == 'program'
        if not is_course_or_program:
            error_msgs.append('Wrong product_type value for UUID: {}'.format(data['uuid']))

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

        return (
            model.everything.filter(**kwrags).exists() if model_name == 'Course'
            else model.objects.filter(**kwrags).exists()
        )

    def check_for_potential_orphans_in_courses(self):
        for geolocation_id in self.updated_geolocations:
            related_course = Course.everything.filter(geolocation__id=geolocation_id).first()
            if not related_course:
                GeoLocation.objects.filter(id=geolocation_id).delete()
                logger.info("Removed orphaned geolocation objects with id: {}".format(geolocation_id))  # lint-amnesty, pylint: disable=logging-format-interpolation

    def log_skipped_items(self):
        if self.skipped_items:
            logger.info("Skipped items:")
            for msg in self.skipped_items:
                logger.error(msg)

    def log_processed_products(self):
        if self.processed_courses:
            logger.info("Successfully updated courses: ")
            for msg in self.processed_courses:
                logger.info(msg)

        if self.processed_programs:
            logger.info("Successfully updated programs: ")
            for msg in self.processed_programs:
                logger.info(msg)
