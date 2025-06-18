"""Mixins related to Data Loaders"""
import csv
import logging
from functools import cache

import unicodecsv
from dateutil.parser import parse
from django.conf import settings
from django.db.models import Q
from django.urls import reverse

from course_discovery.apps.core.utils import serialize_datetime
from course_discovery.apps.course_metadata.choices import CourseRunStatus
from course_discovery.apps.course_metadata.data_loaders.constants import (
    CSV_LOADER_ERROR_LOG_SEQUENCE, CSVIngestionErrorMessages, CSVIngestionErrors
)
from course_discovery.apps.course_metadata.gspread_client import GspreadClient
from course_discovery.apps.course_metadata.models import (
    Collaborator, CourseRun, CourseRunPacing, CourseRunType, CourseType, Organization, ProgramType, Source, Subject
)
from course_discovery.apps.ietf_language_tags.models import LanguageTag

logger = logging.getLogger(__name__)


class DataLoaderMixin:
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

    # The keys are the field names in the csv, and the values correspond to model field names
    LEGAL_REVIEW_REQUIRED_FIELDS__COURSE = {
        "image": "image",
        "long_description": "full_description",
        "short_description": "short_description",
        "what_will_you_learn": "outcome",
        "level_type": "level_type",
        "primary_subject": "subjects",
    }
    # The keys are the field names in the csv, and the values correspond to model field names
    LEGAL_REVIEW_REQUIRED_FIELDS__COURSE_RUN = {
        "publish_date": "go_live_date",
        "minimum_effort": "min_effort",
        "maximum_effort": "max_effort",
        "length": "weeks_to_complete",
    }

    LEGAL_REVIEW_REQUIRED_FIELDS = [
        *LEGAL_REVIEW_REQUIRED_FIELDS__COURSE.keys(),
        *LEGAL_REVIEW_REQUIRED_FIELDS__COURSE_RUN.keys()
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
    def initialize_csv_reader(csv_path, csv_file, use_gspread_client=None, product_type=None, product_source=None):
        """
        Initialize the CSV reader based on the input source (csv_path, csv_file or gspread_client)
        """
        try:
            if use_gspread_client:
                product_type_config = settings.PRODUCT_METADATA_MAPPING[product_type][product_source.slug]
                gspread_client = GspreadClient()
                return list(gspread_client.read_data(product_type_config))
            else:
                # read the file from the provided path; otherwise, use the file received from the config model.
                return list(csv.DictReader(open(csv_path, 'r'))) if csv_path else list(unicodecsv.DictReader(csv_file))
        except FileNotFoundError:
            logger.exception(f"Error opening CSV file at path: {csv_path}")
            raise
        except Exception as e:
            logger.exception(f"Error reading input data source: {e}")
            raise

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

    def create_course_run(self, data, course, course_run_type_uuid, course_type=None, rerun=None):
        """
        Make a course run entry through course run api.
        """
        url = f"{settings.DISCOVERY_BASE_URL}{reverse('api:v1:course_run-list')}"
        request_data = self.create_course_run_api_request_data(data, course, course_run_type_uuid, course_type, rerun)
        response = self.call_course_api('POST', url, request_data)
        if response.status_code not in (200, 201):
            logger.info(f"Course run creation response: {response.content}")
        return response.json()

    def create_course_run_api_request_data(self, data, course, course_run_type_uuid, course_type=None, rerun=None):
        """
        Given a data dictionary, return a reduced data representation in dict
        which will be used as input for course run creation via course run api.
        """
        pricing = self.get_pricing_representation(data['verified_price'], course_type) if not data.get('prices') \
            else data['prices']
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
            logger.info(f"API request failed for url {url} with response: {response.content.decode('utf-8')}")
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
        Given a data dictionary, return a reduced data representation in dict
        which will be used as input for course creation via course api.
        """
        pricing = self.get_pricing_representation(course_data.get('verified_price'), course_type)
        product_source_slug = product_source.slug if product_source else None

        course_run_creation_fields = {
            "pacing_type": self.get_pacing_type(course_data["course_pacing"]),
            "start": self.get_formatted_datetime_string(
                f"{course_data['start_date']} {course_data.get('start_time', '00:00:00')}"
            ),
            "end": self.get_formatted_datetime_string(
                f"{course_data['end_date']} {course_data.get('end_time', '00:00:00')}"
            ),
            "run_type": str(course_run_type_uuid),
            "prices": pricing,
        }

        return {
            'org': course_data['organization'],
            'title': course_data['title'],
            'number': course_data['number'],
            'product_source': product_source_slug,
            'type': str(course_type.uuid),
            'prices': pricing,
            'course_run': course_run_creation_fields,
        }

    def update_course(self, data, course, course_type, is_draft):
        """
        Update the course data.
        """
        course_api_url = reverse('api:v1:course-detail', kwargs={'key': course.uuid})
        url = f"{settings.DISCOVERY_BASE_URL}{course_api_url}?exclude_utm=1"
        request_data = self.update_course_api_request_data(data, course, course_type, is_draft)
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

    def update_course_api_request_data(self, course_data, course, course_type, is_draft):  # pylint: disable=unused-argument
        """Update the course API request data based on the course and draft state."""
        return course_data

    def update_course_run_api_request_data(self, course_run_data, course_run, course_type, is_draft):  # pylint: disable=unused-argument
        """Update the course run API request data based on the run, type, and draft state."""
        return course_run_data

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

    def _validate_and_process_row(self, row, course_title, org_key, allow_empty_tracks=False):
        """
        Validates and processes a single row of course data.

        Args:
            row (dict): The row of course data.
            course_title (str): The title of the course.
            org_key (str): The organization key.
            allow_empty_tracks (bool): A boolean to indicate if empty("") values for course
                                       and course_run enrollment tracks should be considered valid.

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
            course_type = self.get_course_type(row.get("course_enrollment_track", ""))
            if not course_type and not allow_empty_tracks:
                self.log_ingestion_error(
                    CSVIngestionErrors.MISSING_COURSE_TYPE,
                    CSVIngestionErrorMessages.MISSING_COURSE_TYPE.format(
                        course_title=course_title, course_type=row["course_enrollment_track"]
                    ),
                )
                return False, None, None

            course_run_type = self.get_course_run_type(row.get("course_run_enrollment_track", ""))
            if not course_run_type and not allow_empty_tracks:
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

        missing_fields = self.validate_course_data(row, course_type)  # pylint: disable=assignment-from-no-return
        if missing_fields:
            self.log_ingestion_error(
                CSVIngestionErrors.MISSING_REQUIRED_DATA,
                CSVIngestionErrorMessages.MISSING_REQUIRED_DATA.format(
                    course_title=course_title, missing_data=missing_fields
                )
            )
            return False, course_type, course_run_type

        return True, course_type, course_run_type

    @classmethod
    def missing_fields_for_legal_review(cls, course, course_run):
        """
        Returns fields required for legal review that are not present on the course/courserun.
        """

        obj_required_fields = [
            (course, cls.LEGAL_REVIEW_REQUIRED_FIELDS__COURSE),
            (course_run, cls.LEGAL_REVIEW_REQUIRED_FIELDS__COURSE_RUN)
        ]

        missing_fields = []
        for obj, field_list in obj_required_fields:
            for csv_field, model_field in field_list.items():
                if model_field == 'subjects' and not obj.subjects.count():
                    missing_fields.append(csv_field)

                elif not getattr(obj, model_field, ''):
                    missing_fields.append(csv_field)

        return missing_fields

    def validate_course_data(self, data, course_type=None):
        """
        Override this method to validate course data.
        """

    def register_ingestion_error(self, error_key, error_message):
        """
        Helper method to register error log and increase count of ingestion errors.
        """

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

    def process_collaborators(self, collaborators):
        """
        Given a comma-separated string of collaborator names, return the list of collaborator
        UUIDs after processing.

        Processing involves the following:
            * Stripping and deduplicating collaborator names
            * Fetching existing collaborators from the DB in a single query
            * Creating missing collaborators
        """
        collaborator_names = [c.strip() for c in collaborators.split(',') if c.strip()]
        collaborator_names = list(set(collaborator_names))

        existing_collaborators = Collaborator.objects.filter(name__in=collaborator_names)
        existing_collab_map = {collab.name: collab for collab in existing_collaborators}

        collaborator_uuids = []
        for name in collaborator_names:
            if name in existing_collab_map:
                collaborator_obj = existing_collab_map[name]
            else:
                collaborator_obj = Collaborator.objects.create(name=name)
                logger.info(f"A new collaborator '{collaborator_obj.name}' has been created")
            collaborator_uuids.append(str(collaborator_obj.uuid))

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

    def parse_boolean_string(self, input_string):
        input_string = input_string.strip()
        if input_string.lower() == "true":
            return True
        return False

    def parse_comma_separated_values(self, input_string):
        if not input_string.strip():
            return []
        return [value.strip() for value in input_string.split(',')]

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
                    f"Language {language} from provided string {language_str} is either missing "
                    "or an invalid ietf language"
                )
            languages_codes_list.append(language_obj.code)
        return languages_codes_list
