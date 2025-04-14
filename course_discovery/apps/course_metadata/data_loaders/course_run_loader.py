import logging

from course_discovery.apps.course_metadata.data_loaders import AbstractDataLoader
from course_discovery.apps.course_metadata.data_loaders.utils import (
    initialize_csv_reader,
    transform_dict_keys,
    get_formatted_datetime_string,
    extract_seat_prices,
    create_course_run,
    get_course_run_type,
    get_pacing_type
)
from course_discovery.apps.course_metadata.models import CourseRun, CourseRunPacing

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
    def __init__(self, partner, csv_path=None, csv_file=None, use_gspread_client=False):
        """
        Initialize the CourseRunDataLoader.

        Arguments:
            partner: The partner instance.
            api_url: The base URL for the course run API.
            csv_path: Path to the CSV file.
            csv_file: A file object for the CSV file.
            use_gspread_client: If True, use the gspread client to read data.
        """
        super(CourseRunDataLoader, self).__init__(partner)
        self.reader = initialize_csv_reader(csv_path, csv_file, use_gspread_client)
        self.ingestion_summary = {
            'total_runs_count': len(self.reader),
            'success_count': 0,
            'failure_count': 0,
            'errors': []
        }

    def ingest(self):
        logger.info("Starting ingestion of course run CSV data.")
        import pdb
        pdb.set_trace()
        for row in self.reader:
            row = transform_dict_keys(row)

            course_run_key = row.get('last_active_run_key')
            start_date = row.get('start_date')
            end_date = row.get('end_date')
            start_time = row.get('start_time', '00:00:00')
            end_time = row.get('end_time', '00:00:00')
            run_type = row.get('run_type')
            pacing_type = row.get('pacing_type')

            if not course_run_key or not start_date or not end_date or not run_type or not pacing_type:
                error_message = f"Missing required field(s) in row: {row}"
                logger.error(error_message)
                self.ingestion_summary['failure_count'] += 1
                self.ingestion_summary['errors'].append(error_message)
                continue

            try:
                course_run = CourseRun.objects.filter(key=course_run_key).first()
                if not course_run:
                    error_message = f"CourseRun with key '{course_run_key}' not found. Skipping row."
                    logger.error(error_message)
                    self.ingestion_summary['failure_count'] += 1
                    self.ingestion_summary['errors'].append(error_message)
                    continue

                start_datetime = get_formatted_datetime_string(f"{start_date} {start_time}")
                end_datetime = get_formatted_datetime_string(f"{end_date} {end_time}")

                course = course_run.course
                course_run_type_uuid = get_course_run_type(run_type).uuid

                data = {
                    'prices': extract_seat_prices(course_run),
                    'start': start_datetime,
                    'end': end_datetime,
                    'pacing_type': pacing_type,
                }

                _ = create_course_run(
                    self.api_client,
                    data,
                    course,
                    course_run_type_uuid,
                    rerun=course_run_key
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
