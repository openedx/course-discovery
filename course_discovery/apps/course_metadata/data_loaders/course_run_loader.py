import logging
from django.conf import settings
from django.urls import reverse
from functools import cache

from course_discovery.apps.course_metadata.data_loaders import AbstractDataLoader
from course_discovery.apps.course_metadata.data_loaders.utils import (
    initialize_csv_reader,
    transform_dict_keys,
    get_formatted_datetime_string,
    extract_seat_prices
)
from course_discovery.apps.course_metadata.models import CourseRun, CourseRunType, CourseRunPacing

logger = logging.getLogger(__name__)


class CourseRunDataLoader(AbstractDataLoader):
    """
    Data loader to create course runs for existing courses using course run CSV data.
    The CSV must contain:
        - Last Active Run Key
        - Start Date
        - End Date
        - Start Time
        - End Time
        - Run Type
        - Pacing Type
    """
    def __init__(self, partner, api_url, csv_path=None, csv_file=None, use_gspread_client=False):
        """
        Initialize the CourseRunDataLoader.

        Arguments:
            partner: The partner instance.
            api_url: The base URL for the course run API.
            csv_path: Path to the CSV file.
            csv_file: A file object for the CSV file.
            use_gspread_client: If True, use the gspread client to read data.
        """
        super(CourseRunDataLoader, self).__init__(partner, api_url)
        self.reader = initialize_csv_reader(csv_path, csv_file, use_gspread_client)
        self.ingestion_summary = {
            'total_runs_count': len(self.reader),
            'success_count': 0,
            'failure_count': 0,
            'errors': []
        }

    def ingest(self):
        logger.info("Starting ingestion of course run CSV data.")
        for row in self.reader:
            row = transform_dict_keys(row)

            course_run_key = row.get('Last Active Run Key')
            start_date = row.get('Start Date')
            end_date = row.get('End Date')
            start_time = row.get('Start Time', '00:00:00')
            end_time = row.get('End Time', '00:00:00')
            run_type = row.get('Run Type')
            pacing_type = row.get('Pacing Type')

            if not course_run_key or not start_date or not end_date or not run_type or not pacing_type:
                error_message = f"Missing required field(s) in row: {row}"
                logger.error(error_message)
                self.ingestion_summary['failure_count'] += 1
                self.ingestion_summary['errors'].append(error_message)
                continue

            try:
                course_run = CourseRun.objects.filter(key=course_run_key, partner=self.partner).first()
                if not course_run:
                    error_message = f"CourseRun with key '{course_run_key}' not found. Skipping row."
                    logger.error(error_message)
                    self.ingestion_summary['failure_count'] += 1
                    self.ingestion_summary['errors'].append(error_message)
                    continue

                start_datetime = get_formatted_datetime_string(f"{start_date} {start_time}")
                end_datetime = get_formatted_datetime_string(f"{end_date} {end_time}")

                course = course_run.course
                course_type = getattr(course, 'course_type', None)
                course_run_type_uuid = self.get_course_run_type(run_type)

                data = {
                    'prices': extract_seat_prices(course_run),
                    'start': start_datetime,
                    'end': end_datetime,
                    'pacing_type': pacing_type,
                }

                _ = self._create_course_run(
                    data,
                    course,
                    course_type,
                    course_run_type_uuid,
                    course_run_key
                )

                logger.info(f"Successfully created course run for course run key: {course_run_key}")
                self.ingestion_summary['success_count'] += 1
            except Exception as e:
                error_message = f"Exception processing course run key '{course_run_key}': {e}"
                logger.exception(error_message)
                self.ingestion_summary['failure_count'] += 1
                self.ingestion_summary['errors'].append(error_message)

        logger.info("Course run ingestion complete.")
        logger.info(f"Ingestion Summary: {self.ingestion_summary}")
        return self.ingestion_summary

    def _create_course_run(self, data, course, course_type, course_run_type_uuid, rerun=None):
        """
        Make a course run entry through course run API.
        """
        url = f"{settings.DISCOVERY_BASE_URL}{reverse('api:v1:course_run-list')}"
        request_data = self._create_course_run_api_request_data(data, course, course_type, course_run_type_uuid, rerun)
        response = self._call_course_api('POST', url, request_data)
        if response.status_code not in (200, 201):
            logger.info(f"Course run creation response: {response.content}")
        return response.json()

    def _create_course_run_api_request_data(self, data, course, course_type, course_run_type_uuid, rerun=None):
        """
        Given a data dictionary, return a reduced data representation which will be used
        as input for course run creation via the course run API.
        """
        pricing = self.get_pricing_representation(data['prices'], course_type)
        course_run_creation_fields = {
            'pacing_type': self.get_pacing_type(data['pacing_type']),
            'start': data['start'],
            'end': data['end'],
            'run_type': str(course_run_type_uuid),
            'prices': pricing,
            'course': course.key,
        }

        if rerun:
            course_run_creation_fields['rerun'] = rerun
        return course_run_creation_fields

    def _call_course_api(self, method, url, data):
        """
        Helper method to make course and course run API calls.
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

    def get_pricing_representation(self, price, course_type):
        """
        Return dict representation of prices for a given course type.
        """
        prices = {}
        entitlement_types = course_type.entitlement_types.all()
        for entitlement_type in entitlement_types:
            prices.update({entitlement_type.slug: price})
        return prices

    def get_pacing_type(self, pacing):
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

