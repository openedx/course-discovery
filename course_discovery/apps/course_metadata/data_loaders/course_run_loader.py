"""
CourseRunDataLoader for ingesting course runs from a CSV file.

This module defines a loader that creates new CourseRun instances by rerunning existing course runs.
"""

import logging

from course_discovery.apps.course_metadata.choices import CourseRunStatus
from course_discovery.apps.course_metadata.data_loaders import AbstractDataLoader
from course_discovery.apps.course_metadata.data_loaders.constants import (
    CSV_LOADER_ERROR_LOG_SEQUENCE, CSVIngestionErrors
)
from course_discovery.apps.course_metadata.data_loaders.mixins import DataLoaderMixin
from course_discovery.apps.course_metadata.models import CourseRun

logger = logging.getLogger(__name__)


class CourseRunDataLoader(AbstractDataLoader, DataLoaderMixin):
    """
    Loads new CourseRuns from a CSV by rerunning existing course runs.
    """

    BASE_REQUIRED_DATA_FIELDS = ['last_active_run_key', 'start_date', 'end_date', 'run_type', 'pacing_type']

    def __init__(
        self,
        partner,
        api_url=None,
        max_workers=None,
        is_threadsafe=False,
        csv_path=None,
        csv_file=None,
    ):
        """
        Initialize the loader with CSV input and ingestion tracking.
        """
        super().__init__(partner=partner, api_url=api_url, max_workers=max_workers, is_threadsafe=is_threadsafe)
        self.error_logs = {key: [] for key in CSV_LOADER_ERROR_LOG_SEQUENCE}
        self.reader = self.initialize_csv_reader(csv_path, csv_file)
        self.ingestion_summary = {
            'total_runs_count': len(self.reader),
            'success_count': 0,
            'failure_count': 0,
            'errors': [],
            'new_runs': [],
        }

    def ingest(self):
        """
        Perform the ingestion process for each CSV row.
        """
        logger.info("Starting ingestion of course run loader.")

        for index, row in enumerate(self.reader, start=1):
            row = self.transform_dict_keys(row)
            last_active_run_key = row.get('last_active_run_key')
            missing_fields = self.validate_course_data(row)

            if missing_fields:
                self.log_ingestion_error(
                    CSVIngestionErrors.MISSING_REQUIRED_DATA,
                    f"[Row {index}] Missing required field(s) for course run: {last_active_run_key}. "
                    f"The missing data elements are: {missing_fields}"
                )
                continue

            course_run = CourseRun.objects.filter_drafts(key=last_active_run_key).first()
            if not course_run:
                self.log_ingestion_error(
                    CSVIngestionErrors.COURSE_RUN_NOT_FOUND,
                    f"[Row {index}] Last Active Course Run with key '{last_active_run_key}' not found. Skipping row."
                )
                continue

            course = course_run.course
            course_run_type_uuid = self.get_course_run_type(row.get('run_type')).uuid

            data = {
                'prices': self.extract_seat_prices(course_run),
                'start_date': row.get('start_date'),
                'start_time': row.get('start_time', '00:00:00'),
                'end_date': row.get('end_date'),
                'end_time': row.get('end_time', '00:00:00'),
                'course_pacing': row.get('pacing_type'),
            }

            try:
                result = self.create_course_run(
                    data,
                    course,
                    course_run_type_uuid,
                    rerun=last_active_run_key
                )

                if not isinstance(result, dict) or 'key' not in result:
                    raise ValueError(f"Invalid response from create_course_run: {result}")

                new_course_run = CourseRun.everything.filter(key=result['key']).first()

                if not new_course_run:
                    raise LookupError(f"No CourseRun found in DB for key: {result['key']}")

                logger.info(f"[Row {index}] Successfully created rerun {new_course_run.key} for course: {course.title}")
                self.ingestion_summary['success_count'] += 1
                self.ingestion_summary['new_runs'].append(new_course_run.key)

                if row.get('move_to_legal_review', '').lower() == 'true':
                    new_course_run.status = CourseRunStatus.LegalReview
                    new_course_run.save(update_fields=['status'], send_emails=True)

            except (ValueError, LookupError, AttributeError) as e:
                self.log_ingestion_error(
                    CSVIngestionErrors.COURSE_RUN_CREATE_ERROR,
                    f"[Row {index}] Error creating rerun for course '{course.title}': {str(e)}"
                )

        logger.info("Course run ingestion complete.")
        logger.info(f"Ingestion Summary: {self.ingestion_summary}")
        self.render_error_logs(self.error_logs)

        return {
            'summary': self.ingestion_summary,
            'errors': self.error_logs,
        }

    def validate_course_data(self, data, course_type=None):
        """
        Check if required fields are present and non-empty in a CSV row.
        """
        missing = [field for field in self.BASE_REQUIRED_DATA_FIELDS if not data.get(field)]
        return ', '.join(missing) if missing else ''

    def log_ingestion_error(self, error_code, message):
        """
        Log and register an error during ingestion.
        """
        logger.error(message)
        self.register_ingestion_error(error_code, message)

    def register_ingestion_error(self, error_key, error_message):
        """
        Track ingestion failure in the summary and error logs.
        """
        self.ingestion_summary['failure_count'] += 1
        self.error_logs[error_key].append(error_message)
