import logging
from django.conf import settings

from course_discovery.apps.course_metadata.data_loaders import AbstractDataLoader
from course_discovery.apps.course_metadata.data_loaders.utils import initialize_csv_reader, transform_dict_keys, get_formatted_datetime_string
from course_discovery.apps.course_metadata.models import CourseRun

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
            use_gspread_client: If True, use the gspr`ead client to read data.
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

                # Prepare the API request payload.
                payload = {
                    'course': course_run.course.key,
                    'start': start_datetime,
                    'end': end_datetime,
                    'run_type': run_type,
                    'pacing_type': pacing_type,
                }

                # Create URL for the API endpoint. (Assumes reverse lookup)
                url = f"{settings.DISCOVERY_BASE_URL}{reverse('api:v1:course_run-list')}"

                # Make the API request to create a course run.
                response = call_course_api('POST', url, payload)
                if response.status_code in (200, 201):
                    logger.info(f"Successfully created course run for course: {course_key}")
                    self.ingestion_summary['success_count'] += 1
                else:
                    error_message = (
                        f"Failed to create course run for course '{course_key}'. "
                        f"API responded with status {response.status_code} and content: {response.content}"
                    )
                    logger.error(error_message)
                    self.ingestion_summary['failure_count'] += 1
                    self.ingestion_summary['errors'].append(error_message)
            except Exception as e:
                error_message = f"Exception processing course key '{course_key}': {e}"
                logger.exception(error_message)
                self.ingestion_summary['failure_count'] += 1
                self.ingestion_summary['errors'].append(error_message)

        logger.info("Course run ingestion complete.")
        logger.info(f"Ingestion Summary: {self.ingestion_summary}")
        return self.ingestion_summary
