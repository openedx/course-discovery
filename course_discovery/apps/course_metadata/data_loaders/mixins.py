"""Mixins related to Data Loaders"""
import logging
from abc import ABC, abstractmethod
from functools import cache

from dateutil.parser import parse
from django.conf import settings
from django.db.models import Q
from django.urls import reverse

from course_discovery.apps.core.utils import serialize_datetime
from course_discovery.apps.course_metadata.choices import CourseRunStatus
from course_discovery.apps.course_metadata.models import CourseRun, CourseRunPacing, CourseRunType
from course_discovery.apps.course_metadata.data_loaders.constants import (
    CSV_LOADER_ERROR_LOG_SEQUENCE, CSVIngestionErrorMessages, CSVIngestionErrors
)
from course_discovery.apps.course_metadata.gspread_client import GspreadClient
from course_discovery.apps.course_metadata.models import (
    Collaborator, CourseRun, CourseRunPacing, CourseRunType, CourseType, Organization, ProgramType, Source, Subject
)
from course_discovery.apps.ietf_language_tags.models import LanguageTag

logger = logging.getLogger(__name__)


class DataLoaderMixin(ABC):
    """
    Mixin having all the commonly used utility functions for data loaders.
    """
    
    PROGRAM_TYPES = [
        ProgramType.XSERIES,
        ProgramType.MASTERS,
        ProgramType.BACHELORS,
        ProgramType.DOCTORATE,
        ProgramType.LICENSE,
        ProgramType.CERTIFICATE,
        ProgramType.MICROMASTERS,
        ProgramType.MICROBACHELORS,
        ProgramType.PROFESSIONAL_PROGRAM_WL,
        ProgramType.PROFESSIONAL_CERTIFICATE
    ]

     # Addition of a user agent to allow access to data CDNs
    REQUEST_USER_AGENT_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/101.0.4951.64 Safari/537.36'
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        if not hasattr(self, 'api_client') or self.api_client is None:
            raise ValueError("api_client must be set before using DataLoaderMixin.")

    @staticmethod
    def transform_dict_keys(data):
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
            transformed_dict[updated_key] = value
        return transformed_dict

    @staticmethod
    def get_formatted_datetime_string(date_string):
        """
        Return the datetime string into the desired format %Y-%m-%dT%H:%M:%SZ

        Expects `parse_date` which is defined in AbstractDataLoader.
        """
        return serialize_datetime(parse(date_string)) if date_string else None

    @staticmethod
    def extract_seat_prices(course_run):
        """
        Return a dictionary with seat types as keys and their prices as string values.
        Example:
            {
                "audit": "0.00",
                "verified": "100.00"
            }
        """
        prices = {}

        for seat in course_run.seats.all():
            prices[seat.type.slug] = f"{seat.price:.2f}"
        return prices

    def create_course_run(self, data, course, course_type, course_run_type_uuid, rerun=None):
        """
        Make a course run entry through course run api.
        """
        url = f"{settings.DISCOVERY_BASE_URL}{reverse('api:v1:course_run-list')}"
        request_data = self.create_course_run_api_request_data(data, course, course_type, course_run_type_uuid, rerun)
        response = self.call_course_api('POST', url, request_data)
        if response.status_code not in (200, 201):
            logger.info(f"Course run creation response: {response.content}")
        return response.json()

    def create_course_run_api_request_data(self, data, course, course_type, course_run_type_uuid, rerun=None):
        """
        Given a data dictionary, return a reduced data representation in dict
        which will be used as input for course run creation via course run api.
        """
        pricing = self.get_pricing_representation(data['verified_price'], course_type)
        course_run_creation_fields = {
            'pacing_type': self.get_pacing_type(data['course_pacing']),
            'start': self.get_formatted_datetime_string(f"{data['start_date']} {data['start_time']}"),
            'end': self.get_formatted_datetime_string(f"{data['end_date']} {data['end_time']}"),
            'run_type': str(course_run_type_uuid),
            'prices': pricing,
            'course': course.key,
        }

        if rerun:
            course_run_creation_fields['rerun'] = rerun
        return course_run_creation_fields

    def call_course_api(self, method, url, data):
        """
        Helper method to make course and course run api calls.
        """
        response = self.api_client.request(
            method,
            url,
            json=data,
            headers={'content-type': 'application/json'}
        )
        if not response.ok:
            logger.info("API request failed for url {} with response: {}".format(url, response.content.decode('utf-8')))
        response.raise_for_status()
        return response

    @staticmethod
    def get_pacing_type(pacing):
        """
        Return appropriate pacing selection against a provided pacing string.
        """
        if pacing:
            pacing = pacing.lower()

        if pacing == 'instructor-paced':
            return CourseRunPacing.Instructor.value
        elif pacing == 'self-paced':
            return CourseRunPacing.Self.value
        else:
            return None

    @staticmethod
    @cache
    def get_course_run_type(course_run_type_name):
        """
        Retrieve a CourseRunType object, using a cache to avoid redundant queries.

        Args:
            course_run_type_name (str): Course run type name
        """
        try:
            return CourseRunType.objects.get(name=course_run_type_name)
        except CourseRunType.DoesNotExist:
            return None

    @staticmethod
    def get_pricing_representation(price, course_type):
        """
        Return dict representation of prices for a given course type.
        """
        prices = {}
        entitlement_types = course_type.entitlement_types.all()
        for entitlement_type in entitlement_types:
            prices.update({entitlement_type.slug: price})
        return prices

    @staticmethod
    def get_course_key(organization_key, number):
        """
        Given organization key and course number, return course key.
        """
        return '{org}+{number}'.format(org=organization_key, number=number)

    def create_course(self, data, course_type, course_run_type_uuid, product_source=None):
        """
        Make a course entry through course api.
        """
        course_api_url = reverse('api:v1:course-list')
        url = f"{settings.DISCOVERY_BASE_URL}{course_api_url}"

        request_data = self.create_course_api_request_data(data, course_type, course_run_type_uuid, product_source)
        response = self.call_course_api('POST', url, request_data)
        if response.status_code not in (200, 201):
            logger.info(f"Course creation response: {response.content}")
        return response.json()

    def create_course_api_request_data(self, course_data, course_type, course_run_type_uuid, product_source=None):
        """
        Override this method to create course data in their respective loader.
        """
        pass

    def update_course(self, data, course, is_draft):
        """
        Update the course data.
        """
        course_api_url = reverse('api:v1:course-detail', kwargs={'key': course.uuid})
        url = f"{settings.DISCOVERY_BASE_URL}{course_api_url}?exclude_utm=1"
        request_data = self.update_course_api_request_data(data, course, is_draft)
        response = self.call_course_api('PATCH', url, request_data)

        if response.status_code not in (200, 201):
            logger.info(f"Course update response: {response.content}")
        return response.json()

    def update_course_run(self, data, course_run, course_type, is_draft):
        """
        Update the course run data.
        """
        course_run_api_url = reverse('api:v1:course_run-detail', kwargs={'key': course_run.key})
        url = f"{settings.DISCOVERY_BASE_URL}{course_run_api_url}?exclude_utm=1"
        request_data = self.update_course_run_api_request_data(data, course_run, course_type, is_draft)
        response = self.call_course_api('PATCH', url, request_data)
        if response.status_code not in (200, 201):
            logger.info(f"Course run update response: {response.content}")
        return response.json()

    @abstractmethod
    def update_course_api_request_data(self, course_data, course, is_draft):
        """Update the course API request data based on the course and draft state."""
        pass

    @abstractmethod
    def update_course_run_api_request_data(self, course_run_data, course_run, course_type, is_draft):
        """Update the course run API request data based on the run, type, and draft state."""
        pass

    @staticmethod
    def get_draft_flag(course):
        """
        To keep behavior consistent with publisher, draft flag is false only when:
            1. Course run is moved from Unpublished -> Review State
            2. Any of the Course run is in published state
        No 1 is not applicable at the moment as we are changing status via data loaders, so we are sending false
        draft flag to the course_run api directly for now.
        """
        return not CourseRun.objects.filter_drafts(course=course, status=CourseRunStatus.Published).exists()

    @staticmethod
    def add_product_source(course, product_source):
        """
        Associate product source object with provided course object.
        """
        course.product_source = product_source
        if course.official_version:
            course.official_version.product_source = product_source
            course.official_version.save(update_fields=['product_source'])
        course.save(update_fields=['product_source'])

    @staticmethod
    @cache
    def _validate_organization(org_key):
        """
        Helper method to validate the organization key

        Args:
            org_key (str): Organization key

        Returns:
            bool: True if the organization exists, False otherwise
        """
        return Organization.objects.filter(key=org_key).exists()

    def validate_organization(self, org_key, course_title):
        """
        Wrapper method to validate the organization key and log an error if the organization does not exist.

        Args:
            org_key (str): Organization key
            course_title (str): Course title

        Returns:
            bool: True if the organization exists, False otherwise
        """
        if not self._validate_organization(org_key):
            self.log_ingestion_error(
                CSVIngestionErrors.MISSING_ORGANIZATION,
                CSVIngestionErrorMessages.MISSING_ORGANIZATION.format(
                    course_title=course_title, org_key=org_key
                )
            )
            return False
        return True

    @staticmethod
    def get_product_source(product_source):
        """
        Retrieve the product source or raise an exception if product source doesn't exist already
        """
        try:
            return Source.objects.get(slug=product_source)
        except Source.DoesNotExist:
            logger.exception(f"Unable to locate source with slug '{product_source}'")
            raise
    
    @staticmethod
    @cache
    def get_course_type(course_type_name):
        """
        Retrieve a CourseType object, using a cache to avoid redundant queries.

        Args:
            course_type_name (str): Course type name

        Returns:
            CourseType: CourseType object
        """
        try:
            return CourseType.objects.get(name=course_type_name)
        except CourseType.DoesNotExist:
            return None

    def _validate_and_process_row(self, row, course_title, org_key):
        """
        Validates and processes a single row of course data.

        Args:
            row (dict): The row of course data.
            course_title (str): The title of the course.
            org_key (str): The organization key.

        Returns:
            tuple: A tuple containing a boolean indicating validity, course type, and course run type.
        """
        if not self.validate_organization(org_key, course_title):
            return False, None, None

        def validate_course_and_course_run_types(row, course_title):
            """
            Helper method to validate course and course run types.

            Args:
                row (dict): Course data row
                course_title (str): Course title

            Returns:
                bool: True if course and course run types are valid, False otherwise
                CourseType: CourseType object
                CourseRunType: CourseRunType object
            """
            course_type = self.get_course_type(row["course_enrollment_track"])
            if not course_type:
                self.log_ingestion_error(
                    CSVIngestionErrors.MISSING_COURSE_TYPE,
                    CSVIngestionErrorMessages.MISSING_COURSE_TYPE.format(
                        course_title=course_title, course_type=row["course_enrollment_track"]
                    ),
                )
                return False, None, None

            course_run_type = self.get_course_run_type(row["course_run_enrollment_track"])
            if not course_run_type:
                self.log_ingestion_error(
                    CSVIngestionErrors.MISSING_COURSE_RUN_TYPE,
                    CSVIngestionErrorMessages.MISSING_COURSE_RUN_TYPE.format(
                        course_title=course_title, course_run_type=row["course_run_enrollment_track"]
                    ),
                )
                return False, None, None

            return True, course_type, course_run_type

        is_valid, course_type, course_run_type = validate_course_and_course_run_types(row, course_title)
        if not is_valid:
            return False, course_type, course_run_type

        missing_fields = self.validate_course_data(course_type, row)
        if missing_fields:
            self.log_ingestion_error(
                CSVIngestionErrors.MISSING_REQUIRED_DATA,
                CSVIngestionErrorMessages.MISSING_REQUIRED_DATA.format(
                    course_title=course_title, missing_data=missing_fields
                )
            )
            return False, course_type, course_run_type

        return True, course_type, course_run_type

    def validate_course_data(self, course_type, data):
        """
        Override this method to validate course data.
        """
        pass

    def register_ingestion_error(self, error_key, error_message):
        """
        Helper method to register error log and increase count of ingestion errors.
        """
        pass

    def log_ingestion_error(self, error_code, message):
        """
        Log the error message and continue the ingestion process.

        Args:
            error_code: Error code
            message (str): Error message
        """
        logger.error(message)
        self.register_ingestion_error(error_code, message)

    @classmethod
    def clear_caches(cls):
        """
        Clears all LRU caches associated with the class.
        """
        cls.get_course_type.cache_clear()
        cls.get_course_run_type.cache_clear()
        cls._validate_organization.cache_clear()

    def render_error_logs(self, error_logs):
        if any(list(error_logs.values())):
            logger.info("Summarized errors:")
            for error_key in CSV_LOADER_ERROR_LOG_SEQUENCE:
                for msg in error_logs[error_key]:
                    logger.error(msg)
        else:
            logger.info("No errors reported in the ingestion")

    def initialize_csv_reader(self, csv_path, csv_file, use_gspread_client, product_type, product_source):
        """
        Initialize the CSV reader based on the input source (csv_path, csv_file or gspread_client)
        """
        try:
            if use_gspread_client:
                product_type_config = settings.PRODUCT_METADATA_MAPPING[product_type][product_source.slug]
                gspread_client = GspreadClient()
                return list(gspread_client.read_data(product_type_config))
            else:
                # read the file from the provided path; otherwise, use the file received from CSVDataLoaderConfiguration
                return list(csv.DictReader(open(csv_path, 'r'))) if csv_path else list(unicodecsv.DictReader(csv_file))
        except FileNotFoundError:
            logger.exception(f"Error opening CSV file at path: {csv_path}")
            raise
        except Exception as e:
            logger.exception(f"Error reading input data source: {e}")
            raise
    
    def process_collaborators(self, collaborators, course_key):
        """
        Given a comma-separated string of collaborator names, return the list of collaborator
        uuids after processing.

        Processing involves the following
            * Checking if the collaborator value is valid
            * Checking for existence of collaborator in DB
            * Create collaborator if not present
        """
        collaborators = collaborators.split(',')
        collaborators = [collaborator.strip() for collaborator in collaborators if collaborator.strip()]
        collaborator_uuids = []
        for collaborator in collaborators:
            collaborator_obj, created = Collaborator.objects.get_or_create(name=collaborator)
            collaborator_uuids.append(str(collaborator_obj.uuid))
            if created:
                logger.info(f"Collaborator {collaborator} created for course {course_key}")
        return collaborator_uuids

    def get_subject_slugs(self, *subjects):
        """
        Given a list of subject names, convert the subject names into their
        slug representation.
        """
        subject_slugs = []
        subjects = [subject for subject in subjects if subject]
        for subject in subjects:
            try:
                sub_obj = Subject.objects.get(translations__name=subject, translations__language_code='en')
                subject_slugs.append(sub_obj.slug)
            except Subject.DoesNotExist:
                logger.exception(f"Unable to locate subject {subject} in the database. Skipping subject association")
                raise

        return subject_slugs

    def verify_and_get_language_tags(self, language_str):
        """
        Given a string of language tags or names, verify their existence in the database
        and return a list of language codes.
        """
        languages_codes_list = []
        languages_list = language_str.split(",")
        for language in languages_list:
            language = language.strip()
            language_obj = LanguageTag.objects.filter(
                Q(name=language) | Q(code=language)
            ).first()
            if not language_obj:
                raise Exception(  # pylint: disable=broad-exception-raised
                    f"Language {language} from provided string {language_str} is either missing or an invalid ietf language"  # pylint: disable=line-too-long
                )
            languages_codes_list.append(language_obj.code)
        return languages_codes_list
