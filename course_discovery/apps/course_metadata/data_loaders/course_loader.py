"""
Data loader responsible for course data ingestion. It loads course data from a CSV file
and processes it for bulk operations (Create/Update). It also handles the validation of
course and course run data for the specified course type.
"""
import csv
import logging
import unicodecsv


from course_discovery.apps.course_metadata.choices import BulkOperationType, CourseRunStatus
from course_discovery.apps.course_metadata.data_loaders import AbstractDataLoader
from course_discovery.apps.course_metadata.data_loaders.constants import (
    CSV_LOADER_ERROR_LOG_SEQUENCE, CSVIngestionErrorMessages, CSVIngestionErrors
)
from course_discovery.apps.course_metadata.data_loaders.mixins import DataLoaderMixin
from course_discovery.apps.course_metadata.data_loaders.utils import prune_empty_values
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
    LEGAL_REVIEW_REQUIRED_FIELDS__COURSE = [
        "image",
        "long_description",
        "short_description",
        "what_will_you_learn",
        "level_type",
        "primary_subject",
    ]
    LEGAL_REVIEW_REQUIRED_FIELDS__COURSE_RUN = [
        "publish_date",
        "minimum_effort",
        "maximum_effort",
        "length",
    ]
    LEGAL_REVIEW_REQUIRED_FIELDS = [
        *LEGAL_REVIEW_REQUIRED_FIELDS__COURSE,
        *LEGAL_REVIEW_REQUIRED_FIELDS__COURSE_RUN
    ]

    def __init__(
        self, partner, api_url=None, max_workers=None, is_threadsafe=False,
        csv_path=None, csv_file=None, product_source='edx', task_type=None
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
            product_source (str): The source of the product for the courses.
            task_type (str): The type of task to be performed (e.g., 'course_create', 'course_partial_update').
            These task types correspond to values defined in the `BulkOperationType` class.
        """
        super().__init__(
            partner=partner,
            api_url=api_url,
            max_workers=max_workers,
            is_threadsafe=is_threadsafe
        )
        self.error_logs = {key: [] for key in CSV_LOADER_ERROR_LOG_SEQUENCE}
        self.task_type = task_type
        self.product_source = self.get_product_source(product_source)
        self.reader = self.initialize_csv_reader(csv_path=csv_path, csv_file=csv_file)
        self.ingestion_summary = self._initialize_ingestion_summary(
            products_count=len(self.reader)
        )

    @staticmethod
    def initialize_csv_reader(
        csv_path, csv_file, use_gspread_client=False, product_type=None, product_source=None
    ):
        """
        Initialize the CSV reader based on the input source (csv_path, csv_file).
        """
        try:
            if csv_path:
                return list(csv.DictReader(open(csv_path, 'r')))
            return list(unicodecsv.DictReader(csv_file))
        except FileNotFoundError:
            logger.exception(f"Error opening CSV file at path: {csv_path}")
            raise
        except Exception as e:
            logger.exception(f"Error reading input data source: {e}")
            raise

    def _initialize_ingestion_summary(self, products_count=0):
        """
        Initializes the ingestion summary dictionary.

        Returns:
            dict: A dictionary to store the ingestion summary.
        """
        return {
            'total_products_count': products_count,
            'success_count': 0,
            'failure_count': 0,
            'updated_products_count': 0,
            'created_products': [],
            'others': [],
        }

    def ingest(self):
        logger.info(f"Initiating Course Loader for {self.task_type}")
        if self.task_type == BulkOperationType.CourseCreate:
            return self._ingest_course_create()
        elif self.task_type == BulkOperationType.PartialUpdate:
            return self._ingest_partial_update()
        return NotImplementedError(
            f"Task type {self.task_type} is not implemented in CourseLoader."
        )

    def missing_fields_for_legal_review(self, course, course_run, row):
        """
        Returns fields required for legal review during a partial update bulk op.
        """

        obj_required_fields = [
            (course, self.LEGAL_REVIEW_REQUIRED_FIELDS__COURSE),
            (course_run, self.LEGAL_REVIEW_REQUIRED_FIELDS__COURSE_RUN)
        ]

        missing_fields = []

        for obj, field_list in obj_required_fields:
            for field in field_list:
                if not (getattr(obj, field, '') or row.get(field, '').strip()):
                    missing_fields.append(field)

        return missing_fields

    def validate_course_data(self, data, course_type=None):
        """
        Verify the required data key-values for a course type are present in the provided
        data dictionary. It dynamically adjusts the required fields based on the course type
        and legal review action before verifying that all required fields are present.

        Args:
            course_type: The type of the course (e.g., Masters, Audit).
            data (dict): The course data to validate.

        Returns:
            str: A comma-separated string of missing fields if any are missing;
                otherwise, an empty string.
        """

        if self.task_type == BulkOperationType.PartialUpdate:
            return ''

        missing_fields = []
        required_fields = self.BASE_REQUIRED_DATA_FIELDS.copy()
        if data.get('move_to_legal_review') and data.get('move_to_legal_review').lower() == 'true':
            required_fields.extend(self.LEGAL_REVIEW_REQUIRED_FIELDS)
            if course_type.slug == 'masters':
                for field_to_remove in ["long_description", "short_description", "what_will_you_learn"]:
                    required_fields.remove(field_to_remove)

        if course_type.slug != CourseRunType.AUDIT:
            required_fields.extend(['verified_price'])

        for field in required_fields:
            if not (field in data and data[field].strip()):
                missing_fields.append(field)

        if missing_fields:
            return ', '.join(missing_fields)
        return ''
    
    def validate_course_data_partial_update(self, course, course_run, row):
        """
        Perform any validation for partial updates. Currently only verifies that the price is provided
        on a track change from audit -> verified and audit.
        """

        obj_csv_column_list = [(course, 'course_enrollment_track'), (course_run, 'course_run_enrollment_track')]

        for obj, column_name in obj_csv_column_list:
            new_track = row.get(column_name, '')
            if obj and new_track and obj.type.name != new_track and new_track != 'Audit Only':
                price = row.get('verified_price')
                if not price:
                    self.log_ingestion_error(
                        CSVIngestionErrors.MISSING_REQUIRED_DATA,
                        "Price must be provided when changing the track"
                    )
                    return False
        
        return True

    def update_course_api_request_data(self, course_data, course, course_type, is_draft):
        """
        Create and return the request data for making a patch call to update the course.
        """
        collaborator_uuids = self.process_collaborators(course_data.get('collaborators', ''))

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
            'type': str((self.get_course_type(course_data.get('course_enrollment_track')) or course.type).uuid),
            'subjects': subjects,
            'collaborators': collaborator_uuids,
            'prices': self.get_pricing_representation(course_data.get('verified_price'), course_type or course.type),
            'title': course_data.get('title', ''),
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
            'watchers': self.parse_comma_separated_values(course_data.get('watchers', '')),
            'topics': self.parse_comma_separated_values(course_data.get('topics', '')),
        }

        if course_data.get('enterprise_subscription_inclusion', '').strip():
            enterprise_subscription_inclusion = self.parse_boolean_string(course_data.get('enterprise_subscription_inclusion', ''))
            update_course_data['enterprise_subscription_inclusion'] = enterprise_subscription_inclusion

        if self.task_type == BulkOperationType.PartialUpdate:
            prune_empty_values(update_course_data)

        return update_course_data

    def update_course_run_api_request_data(self, course_run_data, course_run, course_type, is_draft):
        """
        Create and return the request data for making a patch call to update the course run.
        """
        def get_datetime_field(date_field, time_field, default_time='00:00:00'):
            """
            Helper function to get the formatted datetime string for a given date and time key.
            """
            date = course_run_data.get(date_field)
            time = course_run_data.get(time_field, default_time) if time_field else ''
            if date:
                return self.get_formatted_datetime_string(f"{date} {time}".strip())
            return None

        program_type = course_run_data.get('expected_program_type')
        content_language = self.verify_and_get_language_tags(course_run_data.get('content_language') or 'en-us')
        transcript_language = self.verify_and_get_language_tags(course_run_data.get('transcript_languages') or 'en-us')

        update_course_run_data = {
            'run_type': str(
                (self.get_course_run_type(course_run_data.get('course_run_enrollment_track')) or course_run.type).uuid
            ),
            'key': course_run.key,
            'prices': self.get_pricing_representation(course_run_data.get('verified_price'), course_type or course_run.course.type),
            'draft': is_draft,
            'content_language': content_language[0],
            'expected_program_name': course_run_data.get('expected_program_name', ''),
            'transcript_languages': transcript_language,
            'go_live_date': self.get_formatted_datetime_string(course_run_data.get('publish_date')),
            'expected_program_type': program_type if program_type in self.PROGRAM_TYPES else None,
            'upgrade_deadline_override': self.get_formatted_datetime_string(
                f"{course_run_data.get('upgrade_deadline_override_date', '')} "
                f"{course_run_data.get('upgrade_deadline_override_time', '')}".strip()
            ),
        }

        if length := course_run_data.get('length', ''):
            update_course_run_data.update({'weeks_to_complete': length})
        if min_effort := course_run_data.get('minimum_effort', ''):
            update_course_run_data.update({'min_effort': min_effort})
        if max_effort := course_run_data.get('maximum_effort', ''):
            update_course_run_data.update({'max_effort': max_effort})

        for field_map in [
            ('start_date', 'start_time', 'start'),
            ('end_date', 'end_time', 'end'),
            ('enrollment_start_date', 'enrollment_start_time', 'enrollment_start'),
            ('enrollment_end_date', 'enrollment_end_time', 'enrollment_end'),
        ]:
            date_field, time_field, db_field_name = field_map
            value = get_datetime_field(date_field, time_field)
            if value:
                update_course_run_data[db_field_name] = value

        if self.task_type == BulkOperationType.PartialUpdate:
            prune_empty_values(update_course_run_data)

        return update_course_run_data

    def download_course_image_assets(self, data, course):
        """
        Downloads image and organization logo assets for the specified course.
        Returns a tuple of flags indicating if image downloaded successfully or not.
        """
        def _downloaded_image(field_name, error_type, error_message_template):
            """
            Helper function to download an image asset and handle exceptions.
            Returns a boolean indicating if an image was downloaded successfully.
            If an exception occurs, it logs the error and returns False else True.
            """
            image_url = data.get(field_name)
            if not image_url:
                return True  # No exception occurred; just skipped

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
                return False

            return True

        is_course_image_downloaded = _downloaded_image(
            field_name='image',
            error_type=CSVIngestionErrors.IMAGE_DOWNLOAD_FAILURE,
            error_message_template=CSVIngestionErrorMessages.IMAGE_DOWNLOAD_FAILURE
        )

        is_organization_logo_override_downloaded = _downloaded_image(
            field_name='organization_logo_override',
            error_type=CSVIngestionErrors.LOGO_IMAGE_DOWNLOAD_FAILURE,
            error_message_template=CSVIngestionErrorMessages.LOGO_IMAGE_DOWNLOAD_FAILURE,
        )

        return is_course_image_downloaded, is_organization_logo_override_downloaded

    def _ingest_course_create(self):  # pylint: disable=too-many-statements
        """
        Ingests course data for course creation.
        """
        created_courses = []
        for row in self.reader:
            row = self.transform_dict_keys(row)
            course_title = row['title']
            logger.info(f'Starting data import flow for {course_title}')
            is_valid, course_type, course_run_type = self._validate_and_process_row(
                row, course_title, org_key=row.get("organization")
            )
            if not is_valid:
                continue
            course_key = self.get_course_key(row['organization'], row['number'])
            if Course.objects.filter_drafts(key=course_key, partner=self.partner).exists():  # pylint: disable=no-else-continue
                logger.warning(f'Course with key {course_key} already exists. Skipping creation.')
                logger.warning(f'Select Correct Operation type for the course: {course_title} - {course_key}')
                self.ingestion_summary['others'].append(
                    f'Course with key {course_key} already exists. Skipping creation.'
                )
            else:
                try:
                    _ = self.create_course(row, course_type, course_run_type.uuid, product_source=self.product_source)
                except Exception as exc:  # pylint: disable=broad-except
                    exception_message = exc
                    if hasattr(exc, 'response'):
                        exception_message = exc.response.content.decode('utf-8')
                    self.log_ingestion_error(
                        CSVIngestionErrors.COURSE_CREATE_ERROR,
                        CSVIngestionErrorMessages.COURSE_CREATE_ERROR.format(
                            course_title=course_title, exception_message=exception_message
                        )
                    )
                    continue

            course = Course.objects.filter_drafts(
                key=course_key, partner=self.partner
            ).select_related('type').first()
            course_run = CourseRun.objects.filter_drafts(course=course).select_related('type').first()
            is_draft = self.get_draft_flag(course=course)
            logger.info(f"Draft flag is set to {is_draft} for the course {course_title}")
            is_course_image_download, is_organization_logo_override_download = self.download_course_image_assets(
                data=row, course=course
            )
            if not (is_course_image_download and is_organization_logo_override_download):
                continue
            try:
                self.update_course(row, course, course_type, is_draft)
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
                course_run.status == CourseRunStatus.Unpublished and
                row.get("move_to_legal_review") and row.get("move_to_legal_review").lower() == "true"
            ):
                # Pushing the run into LegalReview is necessary to ensure that the
                # url slug is correctly generated in subdirectory format
                course_run.status = CourseRunStatus.LegalReview
                try:
                    course_run.save(update_fields=["status"], send_emails=True)
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

            created_courses.append(
                {
                    'course': f'{course.uuid} - {course.title} ({course.key})',
                }
            )
            self.ingestion_summary['success_count'] += 1
            self.ingestion_summary['created_products'].append(f'{course.uuid} - {course.title} ({course.key})')

        self.render_error_logs(self.error_logs)
        self.clear_caches()

        return {
            'summary': self.ingestion_summary,
            'errors': self.error_logs,
        }

    def extract_course_and_course_run(self, row):
        """
        Given a row of data, return the course and course run identified by it
        """
        if row.get('course_run_key', ''):
            course_run = CourseRun.everything.get(draft=True, key=row['course_run_key'])
            course = course_run.course
        else:
            course = Course.everything.get(draft=True, key=row['course_key'])
            course_run = None
        
        return course, course_run

    def _ingest_partial_update(self):  # pylint: disable=too-many-statements
        """
        Ingests course and courserun data for partial updates.
        """
        for row in self.reader:
            row = self.transform_dict_keys(row)
            course_key = row.get('course_key', '')
            course_run_key = row.get('course_run_key', '')
            logger.info(f'Starting partial update flow for course: {course_key} and course_run: {course_run_key}')
            
            ## Retrieve the course and run under consideration
            try:
                course, course_run = self.extract_course_and_course_run(row)
            except CourseRun.DoesNotExist:
                self.log_ingestion_error(
                    CSVIngestionErrors.COURSE_RUN_NOT_FOUND,
                    f"Can not find course run with key: [{course_run_key}]"
                )
                continue
            except Course.DoesNotExist:
                self.log_ingestion_error(
                    CSVIngestionErrors.COURSE_NOT_FOUND,
                    f"Can not find course with key: [{course_key}]"
                )
                continue

            is_valid, course_type, course_run_type = self._validate_and_process_row(
                row, course.title, org_key=course.authoring_organizations.first().key, allow_empty_tracks=True
            )
            is_valid = is_valid and self.validate_course_data_partial_update(course, course_run, row)
            if not is_valid:
                continue

            is_draft = self.get_draft_flag(course=course)
            logger.info(f"Draft flag is set to {is_draft} for the course {course.title}")

            is_course_image_download, is_organization_logo_override_download = self.download_course_image_assets(
                data=row, course=course
            )
            if not (is_course_image_download and is_organization_logo_override_download):
                continue

            try:
                self.update_course(row, course, course_type, is_draft)
            except Exception as exc:  # pylint: disable=broad-except
                exception_message = exc
                if hasattr(exc, 'response'):
                    exception_message = exc.response.content.decode('utf-8')
                self.log_ingestion_error(
                    CSVIngestionErrors.COURSE_UPDATE_ERROR,
                    CSVIngestionErrorMessages.COURSE_UPDATE_ERROR.format(
                        course_title=course.title, exception_message=exception_message
                    )
                )
                continue

            if not course_run:
                self.ingestion_summary['success_count'] += 1
                continue

            is_draft = True if course_run.status == CourseRunStatus.Unpublished and row.get("move_to_legal_review", "").lower() != "true" else is_draft
            logger.info(f"Draft flag is set to {is_draft} for the course run {course_run.key}")

            try:
                self.update_course_run(row, course_run, course_type, is_draft)
            except Exception as exc:  # pylint: disable=broad-except
                exception_message = exc
                if hasattr(exc, 'response'):
                    exception_message = exc.response.content.decode('utf-8')
                self.log_ingestion_error(
                    CSVIngestionErrors.COURSE_RUN_UPDATE_ERROR,
                    CSVIngestionErrorMessages.COURSE_RUN_UPDATE_ERROR.format(
                        course_title=course.title, exception_message=exception_message
                    )
                )
                continue

            course.refresh_from_db()
            course_run.refresh_from_db()

            if (
                course_run.status == CourseRunStatus.Unpublished and
                row.get("move_to_legal_review") and row.get("move_to_legal_review").lower() == "true"
            ):
                if missing_fields:=self.missing_fields_for_legal_review(course, course_run, row):
                    self.log_ingestion_error(
                        CSVIngestionErrors.MISSING_REQUIRED_DATA,
                        CSVIngestionErrorMessages.MISSING_REQUIRED_DATA.format(
                            course_title=course.title, missing_data=missing_fields
                        )
                    )
                    continue

                course_run.status = CourseRunStatus.LegalReview
                course_run.save(update_fields=["status"], send_emails=True)

            self.ingestion_summary['success_count'] += 1

        self.render_error_logs(self.error_logs)
        self.clear_caches()

        return {
            'summary': self.ingestion_summary,
            'errors': self.error_logs,
        }

    def register_ingestion_error(self, error_key, error_message):
        """
        Helper method to register error log and increase count of ingestion errors.
        """
        self.ingestion_summary['failure_count'] += 1
        self.error_logs[error_key].append(error_message)
