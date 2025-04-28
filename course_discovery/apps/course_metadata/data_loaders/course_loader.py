import logging
import csv

from course_discovery.apps.course_metadata.choices import BulkOperationType, CourseRunStatus
from course_discovery.apps.course_metadata.data_loaders import AbstractDataLoader
from course_discovery.apps.course_metadata.data_loaders.constants import (
    CSV_LOADER_ERROR_LOG_SEQUENCE, CSVIngestionErrorMessages, CSVIngestionErrors
)
from course_discovery.apps.course_metadata.data_loaders.mixins import DataLoaderMixin
from course_discovery.apps.course_metadata.models import Course, CourseRun, CourseRunType
from course_discovery.apps.course_metadata.utils import download_and_save_course_image

logger = logging.getLogger(__name__)

class CourseLoader(AbstractDataLoader, DataLoaderMixin):
    """
    Loads course data from a CSV file and process it for bulk operations (Create/Update).
    """
    BASE_REQUIRED_DATA_FIELDS = [
        'organization', 'title', 'number', 'start_date', 'end_date', 'course_pacing',
    ]

    def __init__(
        self, partner, api_url=None, max_workers=None, is_threadsafe=False,
        csv_path=None, csv_file=None, use_gspread_client=None, product_source='edx',
        task_type=None
    ):
        """
        Initializes the CourseLoader with the given parameters.

        Args:
            partner (Partner): The partner associated with the courses.
            api_url (str): The API URL for the partner.
            max_workers (int): The maximum number of workers for concurrent processing.
            is_threadsafe (bool): Indicates if the loader is thread-safe.
            csv_path (str): Path to the CSV file containing course data.
            csv_file (file-like object): File-like object containing course data.
            use_gspread_client (bool): Indicates if gspread client should be used.
            product_type (str): The type of product for the courses.
            product_source (str): The source of the product for the courses.
            task_type (str): The type of task to be performed (e.g., 'course_create', 'course_partial_update').
        """
        super().__init__(partner, api_url, max_workers, is_threadsafe)
        DataLoaderMixin.__init__(self, self.api_client)
        self.error_logs = {key: [] for key in CSV_LOADER_ERROR_LOG_SEQUENCE}
        self.ingestion_summary = self._initialize_ingestion_summary()
        self.product_source = product_source
        self.task_type = task_type
        self.product_source = self.get_product_source(product_source)
        self.reader = self.initialize_csv_reader(csv_path, csv_file, use_gspread_client, None, self.product_source)
        self.ingestion_summary['total_products_count'] = len(self.reader)

    def _initialize_ingestion_summary(self):
        """
        Initializes the ingestion summary dictionary.

        Returns:
            dict: A dictionary to store the ingestion summary.
        """
        ingestion_summary = {
            'total_products_count': 0,
            'success_count': 0,
            'failure_count': 0,
            'updated_products_count': 0,
            'created_products': [],
        }
        return ingestion_summary

    def ingest(self):
        logger.info(f"Initiating Course Loader for {self.task_type}")
        if self.task_type == BulkOperationType.CourseCreate:
            self._ingest_course_create()

    def validate_course_data(self, course_type, data):
        """
        Verify the required data key-values for a course type are present in the provided
        data dictionary and return a comma separated string of missing data fields.
        """
        missing_fields = []
        required_fields = self.BASE_REQUIRED_DATA_FIELDS.copy()
        if data.get('move_to_legal_review') and data.get('move_to_legal_review').lower() == 'true':
            LEGAL_REVIEW_REQUIRED_FIELDS = [
                "image",
                "long_description",
                "short_description",
                "what_you_will_learn",
                "level_type",
                "primary_subject",
                "publish_date",
                "minimum_effort",
                "maximum_effort",
                "length",
            ]
            required_fields.extend(LEGAL_REVIEW_REQUIRED_FIELDS)
            if course_type.slug == 'masters':
                required_fields.remove(
                    'long_description',
                )
                required_fields.remove(
                    'short_description',
                )
                required_fields.remove(
                    'what_you_will_learn',
                )

        if course_type.slug != CourseRunType.AUDIT:
            required_fields.extend(['verified_price'])
        for field in required_fields:
            if not (field in data and data[field]):
                missing_fields.append(field)

        if missing_fields:
            return ', '.join(missing_fields)
        return ''

    def create_course_api_request_data(self, data, course_type, course_run_type_uuid, product_source=None):
        """
        Given a data dictionary, return a reduced data representation in dict
        which will be used as input for course creation via course api.
        """
        pricing = self.get_pricing_representation(data.get('verified_price'), course_type)
        product_source = self.product_source.slug if self.product_source else None

        course_run_creation_fields = {
            'pacing_type': self.get_pacing_type(data['course_pacing']),
            'start': self.get_formatted_datetime_string(f"{data['start_date']} {data.get('start_time', '00:00:00')}"),
            'end': self.get_formatted_datetime_string(f"{data['end_date']} {data.get('end_time', '00:00:00')}"),
            'run_type': str(course_run_type_uuid),
            'prices': pricing,
        }

        return {
            'org': data['organization'],
            'title': data['title'],
            'number': data['number'],
            'product_source': product_source,
            'type': str(course_type.uuid),
            'prices': pricing,
            'course_run': course_run_creation_fields,
        }

    def update_course_api_request_data(self, course_data, course, is_draft):
        """
        Create and return the request data for making a patch call to update the course.
        """
        collaborator_uuids = self.process_collaborators(course_data.get('collaborators', ''), course.key)

        subjects = self.get_subject_slugs(
            course_data.get('primary_subject'),
            course_data.get('secondary_subject'),
            course_data.get('tertiary_subject')
        )

        update_course_data = {
            'draft': is_draft,
            'key': course.key,
            'uuid': str(course.uuid),
            'url_slug': course_data.get('url_slug') if course_data.get('url_slug') else course.active_url_slug,
            'type': str(course.type.uuid),
            'subjects': subjects,
            'collaborators': collaborator_uuids,

            'title': course_data['title'],
            'syllabus_raw': course_data.get('syllabus', ''),
            'level_type': course_data.get('level_type', ''),
            'outcome': course_data.get('what_will_you_learn', ''),
            'faq': course_data.get('frequently_asked_questions', ''),
            'video': {'src': course_data.get('about_video_link', '')},
            'prerequisites_raw': course_data.get('prerequisites', ''),
            'full_description': course_data.get('long_description', ''),
            'short_description': course_data.get('short_description', ''),
            'learner_testimonials': course_data.get('learner_testimonials', ''),
            'additional_information': course_data.get('additional_information', ''),
            'organization_short_code_override': course_data.get('organization_short_code_override', ''),
        }
        return update_course_data

    def update_course_run_api_request_data(self, data, course_run, course_type, is_draft):
        """
        Create and return the request data for making a patch call to update the course run.
        """
        program_type = data.get('expected_program_type')
        content_language = self.verify_and_get_language_tags(data.get('content_language', 'en-us'))
        transcript_language = self.verify_and_get_language_tags(data.get('transcript_languages', 'en-us'))
        registration_deadline = data.get('reg_close_date', '')
        length = data.get('length', '')
        min_effort = data.get('minimum_effort', '')
        max_effort = data.get('maximum_effort', '')

        update_course_run_data = {
            'run_type': str(course_run.type.uuid),
            'key': course_run.key,
            'prices': self.get_pricing_representation(data.get('verified_price'), course_type),
            'draft': is_draft,

            'content_language': content_language[0],
            'expected_program_name': data.get('expected_program_name', ''),
            'transcript_languages': transcript_language,
            'go_live_date': self.get_formatted_datetime_string(data.get('publish_date')),
            'expected_program_type': program_type if program_type in self.PROGRAM_TYPES else None,
            'upgrade_deadline_override': self.get_formatted_datetime_string(
                f"{data.get('upgrade_deadline_override_date', '')} "
                f"{data.get('upgrade_deadline_override_time', '')}".strip()
            ),
        }

        if length:
            update_course_run_data.update({'weeks_to_complete': length})
        if min_effort:
            update_course_run_data.update({'min_effort': min_effort})
        if max_effort:
            update_course_run_data.update({'max_effort': max_effort})

        if registration_deadline:
            update_course_run_data.update({'enrollment_end': self.get_formatted_datetime_string(
                f"{data.get('reg_close_date', '')} "
                f"{data.get('reg_close_time', '')}".strip()
            )})
        return update_course_run_data

    def download_image_assets_of_course(self, data, course):
        """
        Downloads image and organization logo assets for the specified course.
        Returns a tuple of flags indicating if download exceptions occurred.
        """
        def _download_image(field_name, error_type, error_message_template):
            image_url = data.get(field_name)
            if not image_url:
                return False

            is_downloaded = download_and_save_course_image(
                course,
                image_url,
                field_name,
                headers=self.REQUEST_USER_AGENT_HEADERS
            )

            if not is_downloaded:
                self.log_ingestion_error(
                    error_type,
                    error_message_template.format(course_title=course.title)
                )
                return True

            return False

        is_image_download_exception_occured = _download_image(
            field_name='image',
            error_type=CSVIngestionErrors.IMAGE_DOWNLOAD_FAILURE,
            error_message_template=CSVIngestionErrorMessages.IMAGE_DOWNLOAD_FAILURE
        )

        is_organization_logo_download_exception_occured = _download_image(
            field_name='organization_logo_override',
            error_type=CSVIngestionErrors.LOGO_IMAGE_DOWNLOAD_FAILURE,
            error_message_template=CSVIngestionErrorMessages.LOGO_IMAGE_DOWNLOAD_FAILURE,
        )

        return is_image_download_exception_occured, is_organization_logo_download_exception_occured

    def _ingest_course_create(self):
        """
        Ingests course data for course creation.
        """
        created_courses = []
        for row in self.reader:
            row = self.transform_dict_keys(row)
            is_course_created = False
            course_title = row.get('title')
            logger.info(f'Starting data import flow for {course_title}')
            is_valid, course_type, course_run_type = self._validate_and_process_row(row, course_title, org_key=row.get('organization'))
            if not is_valid:
                continue
            course_key = self.get_course_key(row['organization'], row['number'])
            # Check if course already exists
            if Course.objects.filter_drafts(key=course_key, partner=self.partner).exists():
                logger.warning(f'Course with key {course_key} already exists. Skipping creation.')
                logger.warning(f'Select Correct Operation type for the course: {course_title} - {course_key}')
                continue
            else:
                _ = self.create_course(row, course_type, course_run_type.uuid, product_source=self.product_source)
                course = Course.everything.select_related('type').get(key=course_key, partner=self.partner)
                course_run = CourseRun.everything.select_related('type').filter(course=course).first()
                is_course_created = True
                is_draft = self.get_draft_flag(course=course)
                logger.info(f"Draft flag is set to {is_draft} for the course {course_title}")
                (
                    is_image_download_exception_occured,
                    is_organization_logo_download_exception_occured,
                ) = self.download_image_assets_of_course(data=row, course=course)
                if (
                    is_image_download_exception_occured
                    or is_organization_logo_download_exception_occured
                ):
                    continue
                try:
                    self.update_course(row, course, is_draft)
                except Exception as exc:  # pylint: disable=broad-except
                    exception_message = exc
                    if hasattr(exc, 'response'):
                        exception_message = exc.response.content.decode('utf-8')
                    self.log_ingestion_error(
                        CSVIngestionErrors.COURSE_UPDATE_ERROR,
                        CSVIngestionErrorMessages.COURSE_UPDATE_ERROR.format(
                            course_title=course_title, exception_message=exception_message
                        )
                    )
                    continue

                try:
                    self.update_course_run(row, course_run, course_type, is_draft)
                except Exception as exc:  # pylint: disable=broad-except
                    exception_message = exc
                    if hasattr(exc, 'response'):
                        exception_message = exc.response.content.decode('utf-8')
                    self.log_ingestion_error(
                        CSVIngestionErrors.COURSE_RUN_UPDATE_ERROR,
                        CSVIngestionErrorMessages.COURSE_RUN_UPDATE_ERROR.format(
                            course_title=course_title, exception_message=exception_message
                        )
                    )
                    continue

                if (
                    course_run.status == CourseRunStatus.Unpublished
                    and row.get("move_to_legal_review") and row.get("move_to_legal_review").lower() == "true"
                ):
                    # Pushing the run into LegalReview is necessary to ensure that the
                    # url slug is correctly generated in subdirectory format
                    course_run.status = CourseRunStatus.LegalReview
                    course_run.save(update_fields=["status"], send_emails=True)
                created_courses.append(
                    {
                        'course': f'{course.uuid} - {course.title} ({course.key})',
                    }
                )
                self.ingestion_summary['success_count'] += 1

        self.render_error_logs(self.error_logs)
        self.clear_caches()

    def register_ingestion_error(self, error_key, error_message):
        """
        Helper method to register error log and increase count of ingestion errors.
        """
        self.ingestion_summary['failure_count'] += 1
        self.error_logs[error_key].append(error_message)
