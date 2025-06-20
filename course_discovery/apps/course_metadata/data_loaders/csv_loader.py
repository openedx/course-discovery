"""
Data loader responsible for creating course and course runs entries in discovery Database,
creating and updating related objects in Studio, and ecommerce, provided a csv containing the required information.
"""
import logging

from django.conf import settings
from django.db.models import Q
from django.urls import reverse

from course_discovery.apps.course_metadata.choices import (
    CourseRunRestrictionType, CourseRunStatus, ExternalCourseMarketingType, ExternalProductStatus
)
from course_discovery.apps.course_metadata.data_loaders import AbstractDataLoader
from course_discovery.apps.course_metadata.data_loaders.constants import (
    CSV_LOADER_ERROR_LOG_SEQUENCE, CSVIngestionErrorMessages, CSVIngestionErrors
)
from course_discovery.apps.course_metadata.data_loaders.mixins import DataLoaderMixin
from course_discovery.apps.course_metadata.models import AdditionalMetadata, Course, CourseRun, CourseType, Person
from course_discovery.apps.course_metadata.utils import download_and_save_course_image

logger = logging.getLogger(__name__)


class CSVDataLoader(AbstractDataLoader, DataLoaderMixin):

    # list of data fields present as CSV columns that should be present in each row for successful CSV Data ingestion.
    BASE_REQUIRED_DATA_FIELDS = [
        'title', 'number', 'image', 'short_description', 'long_description', 'what_will_you_learn', 'course_level',
        'primary_subject', 'verified_price', 'publish_date', 'start_date', 'start_time', 'end_date',
        'end_time', 'course_pacing', 'minimum_effort', 'maximum_effort', 'length',
        'content_language', 'transcript_language'
    ]

    def __init__(
        self, partner, api_url=None, max_workers=None, is_threadsafe=False,
        csv_path=None, csv_file=None, use_gspread_client=None, product_type='audit', product_source='edx'
    ):
        """
        Arguments:
            * api_url: It is not needed in CSV loader but required as a requirement for AbstractDataLoader.
            * max_workers: Same as api_url, not needed.
            * is_threadsafe: Same case as api_url, not needed.
            * csv_path: Directory link the CSV file whose data is to be ingested
            * csv_file: File object that contains the opened CSV file.
            * use_gspread_client: Boolean flag to identify if Gspread client should be used to read CSV from
            Google sheet link.
            * product_type: course type slug to identify the product type present in CSV
            * product_source: slug of the external source that actually owns the product.
        """
        super().__init__(
            partner=partner,
            api_url=api_url,
            max_workers=max_workers,
            is_threadsafe=is_threadsafe
        )

        self.error_logs = {key: [] for key in CSV_LOADER_ERROR_LOG_SEQUENCE}
        self.ingestion_summary = self._initialize_ingestion_summary()
        self.course_uuids = {}  # to show the discovery course ids for each processed course
        self.product_type = product_type
        self.product_source = self.get_product_source(product_source)
        self.reader = self.initialize_csv_reader(
            csv_path, csv_file, use_gspread_client, self.product_type, self.product_source
        )
        self.ingestion_summary['total_products_count'] = len(self.reader)

    def _initialize_ingestion_summary(self):
        """Initialize the ingestion summary dictionary."""
        return {
            'total_products_count': 0,
            'success_count': 0,
            'failure_count': 0,
            'updated_products_count': 0,
            'created_products': [],
            'archived_products': []
        }

    def ingest(self):  # pylint: disable=too-many-statements
        logger.info("Initiating CSV data loader flow.")
        course_external_identifiers = set()  # store external course ids for each course present in sheet

        for row in self.reader:
            row = self.transform_dict_keys(row)
            course_title = row['title']
            org_key = row['organization']

            # store all external identifiers present in sheet, irrespective of ingestion status
            if 'external_identifier' in row:
                course_external_identifiers.add(row['external_identifier'])

            logger.info(f'Starting data import flow for {course_title}')
            is_valid, course_type, course_run_type = self._validate_and_process_row(row, course_title, org_key)
            if not is_valid:
                continue

            course_key = self.get_course_key(org_key, row['number'])
            course = Course.objects.filter_drafts(key=course_key, partner=self.partner).select_related('type').first()
            is_course_already_ingested = bool(course) and str(course.uuid) in self.course_uuids
            is_course_created = False
            is_course_run_created = False
            course_run_restriction = self._get_course_run_restriction(row)
            is_future_variant = row.get('is_future_variant') == 'True'

            if course:
                try:
                    logger.info(f"Course {course_key} is located in the database.")
                    course_run, is_course_run_created = self._get_or_create_course_run(
                        row, course, course_type, course_run_type.uuid
                    )
                except Exception as exc:  # pylint: disable=broad-except
                    logger.exception(exc)
                    continue
            else:
                logger.info(f"Course key {course_key} could not be found in database, creating the course.")
                try:
                    _ = self.create_course(row, course_type, course_run_type.uuid, self.product_source)
                except Exception as exc:  # pylint: disable=broad-except
                    exception_message = exc
                    if hasattr(exc, 'response'):
                        exception_message = exc.response.content.decode('utf-8')
                    self.log_ingestion_error(
                        CSVIngestionErrors.COURSE_CREATE_ERROR,
                        CSVIngestionErrorMessages.COURSE_CREATE_ERROR.format(
                            course_title=course_title,
                            exception_message=exception_message
                        )
                    )
                    continue

                course = Course.everything.select_related('type').get(key=course_key, partner=self.partner)
                course_run = CourseRun.everything.select_related('type').filter(course=course).first()
                is_course_created = True
                is_course_run_created = True

            is_draft = self.get_draft_flag(course=course)
            logger.info(f"Draft flag is set to {is_draft} for the course {course_title}")

            if not is_course_already_ingested:
                is_downloaded = download_and_save_course_image(
                    course,
                    row['image'],
                    headers=self.REQUEST_USER_AGENT_HEADERS)
                if not is_downloaded:
                    self.log_ingestion_error(
                        CSVIngestionErrors.IMAGE_DOWNLOAD_FAILURE,
                        CSVIngestionErrorMessages.IMAGE_DOWNLOAD_FAILURE.format(course_title=course_title)
                    )
                    continue
                if not is_course_created:
                    self.add_product_source(course, self.product_source)

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

                if row.get('organization_logo_override'):
                    course.refresh_from_db()
                    is_logo_downloaded = download_and_save_course_image(
                        course,
                        row['organization_logo_override'],
                        'organization_logo_override',
                        headers=self.REQUEST_USER_AGENT_HEADERS
                    )
                    if not is_logo_downloaded:
                        self.log_ingestion_error(
                            CSVIngestionErrors.LOGO_IMAGE_DOWNLOAD_FAILURE,
                            CSVIngestionErrorMessages.LOGO_IMAGE_DOWNLOAD_FAILURE.format(
                                course_title=course_title
                            )
                        )

            else:
                try:
                    self._update_course_entitlement_price(
                        data=row, course_uuid=course.uuid, course_type=course_type, is_draft=is_draft,
                    )
                except Exception as exc:  # pylint: disable=broad-except
                    exception_message = exc
                    if hasattr(exc, 'response'):
                        self.log_ingestion_error(
                            CSVIngestionErrors.COURSE_UPDATE_ERROR,
                            CSVIngestionErrorMessages.COURSE_ENTITLEMENT_PRICE_UPDATE_ERROR.format(
                                course_title=course_title, exception_message=exception_message
                            )
                        )
                        continue

            # No need to update the course run if the run is already in the review
            if not course_run.in_review:
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

            course_run.refresh_from_db()

            if course_run.status in [CourseRunStatus.Unpublished, CourseRunStatus.LegalReview,
                                     CourseRunStatus.InternalReview]:
                if course_run.status == CourseRunStatus.Unpublished:
                    # Pushing the run into LegalReview is necessary to ensure that the
                    # url slug is correctly generated in subdirectory format
                    course_run.status = CourseRunStatus.LegalReview
                    course_run.save(update_fields=['status'], send_emails=False)
                self._complete_run_review(row, course_run)

            logger.info(f"Course and course run updated successfully for course key {course_key}")

            self.course_uuids[str(course.uuid)] = {"title": course_title, "price": self._get_course_price(row, course)}

            self._register_successful_ingestion(
                str(course.uuid), str(course_run.variant_id), is_course_created, is_course_run_created,
                is_future_variant, course_run_restriction, course.active_url_slug,
                row.get('external_course_marketing_type', None)
            )

        self._archive_stale_products(course_external_identifiers)
        logger.info("CSV loader ingest pipeline has completed.")

        self.render_error_logs(self.error_logs, CSV_LOADER_ERROR_LOG_SEQUENCE)
        self._render_course_uuids()
        self.clear_caches()

    def _get_course_price(self, row, course):
        """
        Determine the price of the course based on the row data.

        Args:
            row (dict): The data row containing course details.
            course: The course instance.

        Returns:
            float | None: The course price or None if unavailable.
        """
        if row.get("restriction_type", "None") != CourseRunRestrictionType.CustomB2BEnterprise.value:
            return row.get("verified_price")
        return self.course_uuids.get(str(course.uuid), {}).get("price", None)

    def _get_course_run_restriction(self, row):
        return None if row.get('restriction_type', None) == 'None' else row.get('restriction_type', None)

    def _get_or_create_course_run(self, data, course, course_type, course_run_type_uuid):
        """
        Helper method to get or create a course run for external LOB courses.

        This method will first try to find a course run with the given variant_id and if it does not find one,
        it will try to find a course run with the given start and end date. If it does not find a course run with
        either of these, it will create a new course run.

        Args:
            data(dict): Dictionary containing the course run data
            course(Course): Course object
            course_type(CourseType): CourseType object
            course_run_type_uuid(uuid): UUID of the course run type

        Returns:
            course_run(CourseRun): CourseRun object
            is_course_run_created(bool): Boolean indicating if a new course run was created
        """
        is_course_run_created = False

        course_runs = CourseRun.objects.filter_drafts(course=course)
        variant_id = data.get('variant_id', '')
        start_datetime = self.get_formatted_datetime_string(f"{data['start_date']} {data['start_time']}")
        end_datetime = self.get_formatted_datetime_string(f'{data["end_date"]} {data["end_time"]}')

        # Added a sanity check (variant_id__isnull=True) to ensure that a wrong course run with the same schedule is not
        # incorrectly updated. It is possible the runs with same schedule but different restriction types can exist.
        filtered_course_runs = course_runs.filter(
            Q(variant_id=variant_id) |
            (Q(start=start_datetime) & Q(end=end_datetime) & Q(variant_id__isnull=True))
        ).order_by('created')
        course_run = filtered_course_runs.last()

        if not course_run:
            logger.info(
                f'Course Run with variant_id {variant_id} could not be found.'
                f'Creating new course run for course {course.key} with variant_id {variant_id}'
            )
            try:
                last_run = course_runs.last()
                _ = self.create_course_run(data, course, course_run_type_uuid, course_type, last_run.key)
                is_course_run_created = True
            except Exception as exc:
                exception_message = exc
                if hasattr(exc, 'response'):
                    exception_message = exc.response.content.decode('utf-8')
                error_message = CSVIngestionErrorMessages.COURSE_RUN_CREATE_ERROR.format(
                    course_title=course.title,
                    variant_id=variant_id,
                    exception_message=exception_message
                )
                self.register_ingestion_error(CSVIngestionErrors.COURSE_RUN_CREATE_ERROR, exception_message)
                raise Exception(error_message)  # pylint: disable=raise-missing-from
        if not course_run and is_course_run_created:
            course_run = CourseRun.objects.filter_drafts(course=course).order_by('created').last()
        return course_run, is_course_run_created

    def validate_course_data(self, data, course_type=None):
        """
        Verify the required data key-values for a course type are present in the provided
        data dictionary and return a comma separated string of missing data fields.
        """
        missing_fields = []
        required_fields = self.BASE_REQUIRED_DATA_FIELDS.copy()
        if (
                course_type.slug in settings.CSV_LOADER_TYPE_SOURCE_REQUIRED_FIELDS and
                self.product_source.slug in settings.CSV_LOADER_TYPE_SOURCE_REQUIRED_FIELDS[course_type.slug]
        ):
            required_fields.extend(
                settings.CSV_LOADER_TYPE_SOURCE_REQUIRED_FIELDS[course_type.slug][self.product_source.slug]
            )
            # Remove some fields for specific external course marketing type
            external_course_marketing_type = data.get('external_course_marketing_type', '')
            if external_course_marketing_type == ExternalCourseMarketingType.Sprint.value:
                required_fields.remove('certificate_header')
                required_fields.remove('certificate_text')

        for field in required_fields:
            if not (field in data and data[field]):
                missing_fields.append(settings.GEAG_API_INGESTION_FIELDS_MAPPING.get(field) or field)

        if missing_fields:
            return ', '.join(missing_fields)
        return ''

    def _render_course_uuids(self):
        if self.course_uuids:
            logger.info("Course UUIDs:")
            for course_uuid, course_dict in self.course_uuids.items():
                logger.info(f"{course_uuid}:{course_dict['title']}")

    def register_ingestion_error(self, error_key, error_message):
        """
        Helper method to register error log and increase count of ingestion errors.
        """
        self.ingestion_summary['failure_count'] += 1
        self.error_logs[error_key].append(error_message)

    def get_ingestion_stats(self):
        return {
            **self.ingestion_summary,
            'created_products_count': len(self.ingestion_summary['created_products']),
            'archived_products_count': len(self.ingestion_summary['archived_products']),
            'errors': self.error_logs
        }

    def _register_successful_ingestion(
        self,
        course_uuid,
        course_run_variant_id,
        is_course_created,
        is_course_run_created,
        is_future_variant,
        course_run_restriction='None',
        active_url_slug='',
        external_course_marketing_type=None
    ):
        """
        Register the summary of a successful ingestion.
        """
        self.ingestion_summary['success_count'] += 1
        if is_course_created or is_course_run_created:
            self.ingestion_summary['created_products'].append(
                {
                    'uuid': course_uuid,
                    'external_course_marketing_type': external_course_marketing_type,
                    'url_slug': active_url_slug,
                    'rerun': is_course_run_created,
                    'course_run_variant_id': course_run_variant_id,
                    'restriction_type': course_run_restriction,
                    'is_future_variant': is_future_variant
                }
            )
        else:
            self.ingestion_summary['updated_products_count'] += 1

    def _archive_stale_products(self, course_external_identifiers):
        """
        This method checks diff between products in discovery vs 2U sheets
        and archive the ones which are not incoming anymore.
        """
        if self.product_type not in [CourseType.EXECUTIVE_EDUCATION_2U, CourseType.BOOTCAMP_2U]:
            return

        all_product_additional_metadatas = AdditionalMetadata.objects.filter(
            related_courses__type__slug=self.product_type,
            related_courses__product_source=self.product_source,
            product_status=ExternalProductStatus.Published.value,
        ).values_list('external_identifier', flat=True)

        archived_products = set(all_product_additional_metadatas).difference(course_external_identifiers)
        archived_products_queryset = AdditionalMetadata.objects.filter(external_identifier__in=archived_products)
        archived_products_queryset.update(product_status=ExternalProductStatus.Archived)
        self.ingestion_summary['archived_products'] = list(archived_products)

        logger.info(
            f"Archived {len(archived_products)} products in CSV Ingestion for source {self.product_source.slug} and "
            f"product type {self.product_type}."
        )
        logger.info("Archived Courses External Identifiers:")
        for archived_product in archived_products:
            logger.info(archived_product)

    def update_course_api_request_data(self, course_data, course, course_type, is_draft):
        """
        Create and return the request data for making a patch call to update the course.
        """
        collaborator_uuids = self.process_collaborators(course_data.get('collaborators', ''))
        price = (
            self.get_pricing_representation(course_data['verified_price'], course.type)
            if course_data.get('restriction_type', 'None') != CourseRunRestrictionType.CustomB2BEnterprise.value else {}
        )

        subjects = self.get_subject_slugs(
            course_data.get('primary_subject'),
            course_data.get('secondary_subject'),
            course_data.get('tertiary_subject')
        )

        update_course_data = {
            'draft': is_draft,
            'key': course.key,
            'uuid': str(course.uuid),
            'url_slug': course.active_url_slug,
            'type': str(course.type.uuid),
            'subjects': subjects,
            'collaborators': collaborator_uuids,
            'prices': price,

            'title': course_data['title'],
            'syllabus_raw': course_data.get('syllabus', ''),
            'level_type': course_data['course_level'],
            'outcome': course_data['what_will_you_learn'],
            'faq': course_data.get('frequently_asked_questions', ''),
            'video': {'src': course_data.get('about_video_link', '')},
            'prerequisites_raw': course_data.get('prerequisites', ''),
            'full_description': course_data['long_description'],
            'short_description': course_data['short_description'],
            'additional_metadata': self.get_additional_metadata_dict(course_data, course.type.slug),
            'learner_testimonials': course_data.get('learner_testimonials', ''),
            'additional_information': course_data.get('additional_information', ''),
            'organization_short_code_override': course_data.get('organization_short_code_override', ''),
        }
        return update_course_data

    def update_course_run_api_request_data(self, course_run_data, course_run, course_type, is_draft):
        """
        Create and return the request data for making a patch call to update the course run.
        """
        program_type = course_run_data.get('expected_program_type')
        staff_uuids = self.process_staff_names(course_run_data.get('staff', ''), course_run.key)
        content_language = self.verify_and_get_language_tags(course_run_data['content_language'])
        transcript_language = self.verify_and_get_language_tags(course_run_data['transcript_language'])
        registration_deadline = course_run_data.get('reg_close_date', '')
        variant_id = course_run_data.get('variant_id', '')
        restriction_type = course_run_data.get('restriction_type', None)

        update_course_run_data = {
            'run_type': str(course_run.type.uuid),
            'key': course_run.key,
            'prices': self.get_pricing_representation(course_run_data['verified_price'], course_type),
            'staff': staff_uuids,
            'draft': is_draft,

            'weeks_to_complete': course_run_data['length'],
            'min_effort': course_run_data['minimum_effort'],
            'max_effort': course_run_data['maximum_effort'],
            'content_language': content_language[0],
            'expected_program_name': course_run_data.get('expected_program_name', ''),
            'transcript_languages': transcript_language,
            'go_live_date': self.get_formatted_datetime_string(course_run_data['publish_date']),
            'expected_program_type': program_type if program_type in self.PROGRAM_TYPES else None,
            'upgrade_deadline_override': self.get_formatted_datetime_string(
                f"{course_run_data.get('upgrade_deadline_override_date', '')} "
                f"{course_run_data.get('upgrade_deadline_override_time', '')}".strip()
            ),
        }
        if fix_price := course_run_data.get('fixed_price_usd', ''):
            update_course_run_data['fixed_price_usd'] = fix_price

        if registration_deadline:
            update_course_run_data.update({'enrollment_end': self.get_formatted_datetime_string(
                f"{course_run_data['reg_close_date']} {course_run_data['reg_close_time']}"
            )})
        if variant_id:
            update_course_run_data.update({'variant_id': variant_id})
        if restriction_type and restriction_type != 'None':
            update_course_run_data.update({'restriction_type': restriction_type})
        return update_course_run_data

    def _update_course_entitlement_price(self, data, course_uuid, course_type, is_draft=False):
        """
        Helper method to update the entitlement price for a course if the verified price differs from the current price
        and the restriction type is not `CustomB2BEnterprise`.
        """
        course_data = self.course_uuids.get(str(course_uuid), {})
        restriction_type = data.get("restriction_type", "None")

        verified_price = data.get("verified_price")
        if (
            course_data.get("price") == verified_price or
            restriction_type == CourseRunRestrictionType.CustomB2BEnterprise.value
        ):
            return None

        course_api_url = reverse('api:v1:course-detail', kwargs={'key': course_uuid})
        url = f"{settings.DISCOVERY_BASE_URL}{course_api_url}"
        pricing = (
            self.get_pricing_representation(data['verified_price'], course_type)
        )

        request_data = {
            'draft': is_draft,
            'title': data['title'],
            'prices': pricing,
        }
        response = self.call_course_api('PATCH', url, request_data)
        if response.status_code not in (200, 201):
            logger.info(f'Entitlement price update response: {response.content}')
        return response.json()

    def _complete_run_review(self, data, course_run):
        """
        Complete the review phase of the course run and publish(internally by model save) if applicable.
        """
        has_ofac_restrictions = data.get(
            'course_embargo_(ofac)_restriction_text_added_to_the_faq_section', ''
        ).lower() in ['yes', '1', 'true']
        ofac_comment = data.get('ofac_comment', '')
        course_run.complete_review_phase(has_ofac_restrictions, ofac_comment)

    def process_staff_names(self, staff_names, course_run_key):
        """
        Given a comma-separated string of staff names, return the list of staff
        uuids after processing.

        Processing involves the following
            * Checking if the staff value is valid
            * Checking for existence of staff member in DB
            * Create staff if not present
        """

        staff_names_list = staff_names.split(',')
        staff_names_list = [staff_name for staff_name in staff_names_list if staff_name.strip()]
        staff_uuids = []

        # TODO: This is a fragile approach. It is possible for two people to have same name within a partner.
        # TODO: CSV would need to provide more information to identify staff members from other than names
        for staff_name in staff_names_list:
            person, created = Person.objects.get_or_create(
                partner=self.partner,
                given_name=staff_name
            )
            staff_uuids.append(str(person.uuid))
            if created:
                logger.info(f"Staff with name {staff_name} has been created for course run {course_run_key}")
        return staff_uuids

    def process_heading_blurb(self, heading, blurb):
        """
        Process and return a representation of dict object, if applicable, for header and blurb fields.
        """
        if not (heading or blurb):
            return ''
        else:
            return {
                'heading': heading,
                'blurb': blurb
            }

    def process_stats(self, stat1, stat1_text, stat2, stat2_text):
        """
        Return a list of stat/fact dicts if valid input values are provided.
        """
        return [
            stat for stat in [
                self.process_heading_blurb(stat1, stat1_text),
                self.process_heading_blurb(stat2, stat2_text),
            ] if stat
        ]

    def process_meta_information(self, meta_title, meta_description, meta_keywords):
        """
        Return a dict containing processed product meta information.
        """
        if not any([meta_title, meta_description, meta_keywords]):
            return {}

        return {
            'title': meta_title,
            'description': meta_description,
            'keywords': [keyword.strip() for keyword in meta_keywords.split(',')] if meta_keywords else []
        }

    def process_taxi_form_information(self, form_id, post_submit_url):
        """
        Return a dict containing processed product taxi form information.
        """
        if not all([form_id, post_submit_url]):
            return {}

        return {
            'form_id': form_id,
            'post_submit_url': post_submit_url,
        }

    def get_additional_metadata_dict(self, data, type_slug):
        """
        Return the appropriate additional metadata dict representation, skipping the keys that are not
        present in the input data dict.
        """
        if type_slug not in [CourseType.EXECUTIVE_EDUCATION_2U, CourseType.BOOTCAMP_2U]:
            return {}

        taxi_form = self.process_taxi_form_information(
            data.get('taxi_form_id', ''), data.get('post_submit_url', '')
        )
        additional_metadata = {
            'external_url': data['redirect_url'],
            'external_identifier': data['external_identifier'],
            'start_date': self.get_formatted_datetime_string(f"{data['start_date']} {data['start_time']}"),
            'end_date': self.get_formatted_datetime_string(f"{data['end_date']} {data['end_time']}"),
            'product_status': ExternalProductStatus.Published,  # By-default, the product status is set to published.
        }
        lead_capture_url = data.get('lead_capture_form_url', '')
        organic_url = data.get('organic_url', '')
        certificate_info = self.process_heading_blurb(
            data.get('certificate_header', ''),
            data.get('certificate_text', '')
        )
        facts = self.process_stats(
            data.get('stat1', ''),
            data.get('stat1_text', ''),
            data.get('stat2', ''),
            data.get('stat2_text', ''),
        )
        registration_deadline = data.get('reg_close_date', '')
        variant_id = data.get('variant_id', '')
        external_course_marketing_type = data.get('external_course_marketing_type', '')
        if lead_capture_url:
            additional_metadata.update({'lead_capture_form_url': lead_capture_url})
        if organic_url:
            additional_metadata.update({'organic_url': organic_url})
        if certificate_info:
            additional_metadata.update({'certificate_info': certificate_info})
        if facts:
            additional_metadata.update({'facts': facts})
        if registration_deadline:
            additional_metadata.update({'registration_deadline': self.get_formatted_datetime_string(
                f"{data['reg_close_date']} {data['reg_close_time']}"
            )})
        if variant_id:
            additional_metadata.update({'variant_id': variant_id})
        if type_slug == CourseType.EXECUTIVE_EDUCATION_2U:
            additional_metadata.update({'product_meta': self.process_meta_information(
                data.get('meta_title', ''),
                data.get('meta_description', ''),
                data.get('meta_keywords', '')
            )})
        if external_course_marketing_type in dict(ExternalCourseMarketingType.choices):
            additional_metadata.update({'external_course_marketing_type': external_course_marketing_type})
        if taxi_form:
            additional_metadata.update({'taxi_form': taxi_form})
        return additional_metadata
