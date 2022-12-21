"""
Data loader responsible for creating course and course runs entries in discovery Database,
creating and updating related objects in Studio, and ecommerce, provided a csv containing the required information.
"""
import csv
import logging

import unicodecsv
from django.conf import settings
from django.db.models import Q
from django.urls import reverse

from course_discovery.apps.core.utils import serialize_datetime
from course_discovery.apps.course_metadata.choices import CourseRunStatus, ExternalProductStatus
from course_discovery.apps.course_metadata.data_loaders import AbstractDataLoader
from course_discovery.apps.course_metadata.data_loaders.constants import (
    CSV_LOADER_ERROR_LOG_SEQUENCE, CSVIngestionErrorMessages, CSVIngestionErrors
)
from course_discovery.apps.course_metadata.gspread_client import GspreadClient
from course_discovery.apps.course_metadata.models import (
    AdditionalMetadata, Collaborator, Course, CourseRun, CourseRunPacing, CourseRunType, CourseType, Organization,
    Person, ProgramType, Subject
)
from course_discovery.apps.course_metadata.utils import download_and_save_course_image
from course_discovery.apps.ietf_language_tags.models import LanguageTag

logger = logging.getLogger(__name__)


class CSVDataLoader(AbstractDataLoader):

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

    # list of data fields (present as CSV columns) that should be present in each row
    BASE_REQUIRED_DATA_FIELDS = [
        'title', 'number', 'image', 'short_description', 'long_description', 'what_will_you_learn', 'course_level',
        'primary_subject', 'verified_price', 'syllabus', 'publish_date', 'start_date', 'start_time', 'end_date',
        'end_time', 'course_pacing', 'minimum_effort', 'maximum_effort', 'length',
        'content_language', 'transcript_language'
    ]

    EXECUTIVE_EDUCATION_REQUIRED_FIELDS = BASE_REQUIRED_DATA_FIELDS + [
        'redirect_url', 'organic_url', 'external_identifier', 'lead_capture_form_url', 'certificate_header',
        'certificate_text', 'stat1', 'stat1_text', 'stat2', 'stat2_text', 'frequently_asked_questions',
        'reg_close_date', 'reg_close_time', 'variant_id',
    ]

    BOOTCAMP_REQUIRED_FIELDS = BASE_REQUIRED_DATA_FIELDS + [
        'redirect_url', 'organic_url', 'external_identifier',
    ]

    def __init__(
        self, partner, api_url=None, max_workers=None, is_threadsafe=False,
        csv_path=None, csv_file=None, args_from_env=None, product_type=None
    ):
        super().__init__(partner, api_url, max_workers, is_threadsafe)

        self.error_logs = {}
        self.ingestion_summary = {
            'total_products_count': 0,
            'success_count': 0,
            'failure_count': 0,
            'updated_products_count': 0,
            'created_products': [],
            'archived_products': []
        }
        self.course_uuids = {}  # to show the discovery course ids for each processed course
        self.product_type = product_type

        for error_log_key in CSV_LOADER_ERROR_LOG_SEQUENCE:
            self.error_logs.setdefault(error_log_key, [])

        try:
            if args_from_env:
                # TODO: add unit tests
                product_type_config = settings.PRODUCT_METADATA_MAPPING[product_type]
                gspread_client = GspreadClient()
                self.reader = gspread_client.read_data(product_type_config)
            else:
                # Read file from the path if given. Otherwise, read from the file
                # received from CSVDataLoaderConfiguration.
                self.reader = csv.DictReader(open(csv_path, 'r')) if csv_path \
                    else list(unicodecsv.DictReader(csv_file))  # lint-amnesty, pylint: disable=consider-using-with
        except FileNotFoundError:
            logger.exception("Error opening csv file at path {}".format(csv_path))  # lint-amnesty, pylint: disable=logging-format-interpolation
            raise  # re-raising exception to avoid moving the code flow
        except Exception:
            logger.exception("Error reading the input data source")
            raise  # re-raising exception to avoid moving the code flow
        else:
            self.reader = list(self.reader)
            self.ingestion_summary['total_products_count'] = len(self.reader)

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

            logger.info('Starting data import flow for {}'.format(course_title))  # lint-amnesty, pylint: disable=logging-format-interpolation
            if not Organization.objects.filter(key=org_key).exists():
                error_message = CSVIngestionErrorMessages.MISSING_ORGANIZATION.format(
                    org_key=org_key,
                    course_title=course_title,
                )
                logger.error(error_message)
                self._register_ingestion_error(CSVIngestionErrors.MISSING_ORGANIZATION, error_message)
                continue

            try:
                course_type = CourseType.objects.get(name=row['course_enrollment_track'])
                course_run_type = CourseRunType.objects.get(name=row['course_run_enrollment_track'])
            except CourseType.DoesNotExist:
                error_message = CSVIngestionErrorMessages.MISSING_COURSE_TYPE.format(
                    course_title=course_title, course_type=row['course_enrollment_track']
                )
                logger.exception(error_message)
                self._register_ingestion_error(CSVIngestionErrors.MISSING_COURSE_TYPE, error_message)
                continue
            except CourseRunType.DoesNotExist:
                error_message = CSVIngestionErrorMessages.MISSING_COURSE_RUN_TYPE.format(
                    course_title=course_title, course_run_type=row['course_run_enrollment_track']
                )
                logger.exception(error_message)
                self._register_ingestion_error(CSVIngestionErrors.MISSING_COURSE_RUN_TYPE, error_message)
                continue

            missing_fields = self.validate_course_data(course_type, row)
            if missing_fields:
                error_message = CSVIngestionErrorMessages.MISSING_REQUIRED_DATA.format(
                    course_title=course_title, missing_data=missing_fields
                )
                logger.error(error_message)
                self._register_ingestion_error(CSVIngestionErrors.MISSING_REQUIRED_DATA, error_message)
                continue

            course_key = self.get_course_key(org_key, row['number'])
            course = Course.objects.filter_drafts(key=course_key, partner=self.partner).first()
            is_course_created = False

            if course:
                course_run = CourseRun.objects.filter_drafts(course=course).first()
                logger.info("Course {} is located in the database.".format(course_key))  # lint-amnesty, pylint: disable=logging-format-interpolation
            else:
                logger.info("Course key {} could not be found in database, creating the course.".format(course_key))  # lint-amnesty, pylint: disable=logging-format-interpolation
                try:
                    _ = self._create_course(row, course_type, course_run_type.uuid)
                except Exception as exc:  # pylint: disable=broad-except
                    exception_message = exc
                    if hasattr(exc, 'response'):
                        exception_message = exc.response.content.decode('utf-8')
                    error_message = CSVIngestionErrorMessages.COURSE_CREATE_ERROR.format(
                        course_title=course_title,
                        exception_message=exception_message
                    )
                    logger.exception(error_message)
                    self._register_ingestion_error(CSVIngestionErrors.COURSE_CREATE_ERROR, error_message)
                    continue

                course = Course.everything.get(key=course_key, partner=self.partner)
                course_run = CourseRun.everything.filter(course=course).first()
                is_course_created = True

            is_downloaded = download_and_save_course_image(
                course,
                row['image'],
                # TODO: Temporary addition of User agent to allow access to data CDNs
                headers={
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                                  '(KHTML, like Gecko) Chrome/101.0.4951.64 Safari/537.36'
                })
            if not is_downloaded:
                error_message = CSVIngestionErrorMessages.IMAGE_DOWNLOAD_FAILURE.format(course_title=course_title)
                logger.error(error_message)
                self._register_ingestion_error(CSVIngestionErrors.IMAGE_DOWNLOAD_FAILURE, error_message)
                continue

            is_draft = self.get_draft_flag(course_run)
            logger.info(f"Draft flag is set to {is_draft} for the course {course_title}")

            try:
                self._update_course(row, course, is_draft)
            except Exception as exc:  # pylint: disable=broad-except
                exception_message = exc
                if hasattr(exc, 'response'):
                    exception_message = exc.response.content.decode('utf-8')
                error_message = CSVIngestionErrorMessages.COURSE_UPDATE_ERROR.format(
                    course_title=course_title,
                    exception_message=exception_message
                )
                logger.exception(error_message)
                self._register_ingestion_error(CSVIngestionErrors.COURSE_UPDATE_ERROR, error_message)
                continue

            if row.get('organization_logo_override'):
                course.refresh_from_db()
                is_logo_downloaded = download_and_save_course_image(
                    course,
                    row['organization_logo_override'],
                    'organization_logo_override',
                    # TODO: Temporary addition of User agent to allow access to data CDNs
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                                      '(KHTML, like Gecko) Chrome/101.0.4951.64 Safari/537.36'
                    }
                )
                if not is_logo_downloaded:
                    error_message = CSVIngestionErrorMessages.LOGO_IMAGE_DOWNLOAD_FAILURE.format(
                        course_title=course_title
                    )
                    logger.error(error_message)
                    self._register_ingestion_error(CSVIngestionErrors.LOGO_IMAGE_DOWNLOAD_FAILURE, error_message)

            # No need to update the course run if the run is already in the review
            if not course_run.in_review:
                try:
                    self._update_course_run(row, course_run, course_type, is_draft)
                except Exception as exc:  # pylint: disable=broad-except
                    exception_message = exc
                    if hasattr(exc, 'response'):
                        exception_message = exc.response.content.decode('utf-8')
                    error_message = CSVIngestionErrorMessages.COURSE_RUN_UPDATE_ERROR.format(
                        course_title=course_title,
                        exception_message=exception_message
                    )
                    logger.exception(error_message)
                    self._register_ingestion_error(CSVIngestionErrors.COURSE_RUN_UPDATE_ERROR, error_message)
                    continue

            logger.info("Course and course run updated successfully for course key {}".format(course_key))  # lint-amnesty, pylint: disable=logging-format-interpolation
            self.course_uuids[str(course.uuid)] = course_title
            self._register_successful_ingestion(str(course.uuid), is_course_created)

        self._archive_stale_products(course_external_identifiers)
        logger.info("CSV loader ingest pipeline has completed.")

        self._render_error_logs()
        self._render_course_uuids()

    def validate_course_data(self, course_type, data):
        """
        Verify the required data key-values for a course type are present in the provided
        data dictionary and return a comma separated string of missing data fields.
        """
        missing_fields = []
        required_fields = self.BASE_REQUIRED_DATA_FIELDS
        if course_type.slug == CourseType.EXECUTIVE_EDUCATION_2U:
            required_fields = self.EXECUTIVE_EDUCATION_REQUIRED_FIELDS
        elif course_type.slug == CourseType.BOOTCAMP_2U:
            required_fields = self.BOOTCAMP_REQUIRED_FIELDS

        for field in required_fields:
            if not (field in data and data[field]):
                missing_fields.append(field)

        if missing_fields:
            return ', '.join(missing_fields)
        return ''

    def _render_error_logs(self):
        if any(list(self.error_logs.values())):
            logger.info("Summarized errors:")
            for error_key in CSV_LOADER_ERROR_LOG_SEQUENCE:
                for msg in self.error_logs[error_key]:
                    logger.error(msg)
        else:
            logger.info("No errors reported in the ingestion")

    def _render_course_uuids(self):
        if self.course_uuids:
            logger.info("Course UUIDs:")
            for course_uuid, title in self.course_uuids.items():
                logger.info(
                    "{}:{}".format(course_uuid, title))  # lint-amnesty, pylint: disable=logging-format-interpolation

    def _register_ingestion_error(self, error_key, error_message):
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

    def _register_successful_ingestion(self, course_uuid, created):
        """
        Register the summary of a successful ingestion.
        """
        self.ingestion_summary['success_count'] += 1
        if created:
            self.ingestion_summary['created_products'].append(course_uuid)
        else:
            self.ingestion_summary['updated_products_count'] += 1

    def _create_course_api_request_data(self, data, course_type, course_run_type_uuid):
        """
        Given a data dictionary, return a reduced data representation in dict
        which will be used as input for course creation via course api.
        """
        pricing = self.get_pricing_representation(data['verified_price'], course_type)

        course_run_creation_fields = {
            'pacing_type': self.get_pacing_type(data['course_pacing']),
            'start': self.get_formatted_datetime_string(f"{data['start_date']} {data['start_time']}"),
            'end': self.get_formatted_datetime_string(f"{data['end_date']} {data['end_time']}"),
            'run_type': str(course_run_type_uuid),
            'prices': pricing,
        }
        return {
            'org': data['organization'],
            'title': data['title'],
            'number': data['number'],
            'type': str(course_type.uuid),
            'prices': pricing,
            'course_run': course_run_creation_fields
        }

    def get_draft_flag(self, course_run):
        """
        To keep behavior of CSV loader consistent with publisher, draft flag is false only when:
            1. Course run is moved from Unpublished -> Review State
            2. Any of the Course run is in published state
        No 1 is not applicable at the moment. For 2, CSV loader right now only expects
        one course run for each course, hence the status of the single fetched course run is checked.
        """
        return not course_run.status == CourseRunStatus.Published

    def _archive_stale_products(self, course_external_identifiers):
        """
        This method checks diff between products in discovery vs 2U sheets
        and archive the ones which are not incoming anymore.
        """
        if self.product_type is None:
            return

        product_type_slug_map = {
            'EXECUTIVE_EDUCATION': CourseType.EXECUTIVE_EDUCATION_2U,
            'BOOTCAMPS': CourseType.BOOTCAMP_2U
        }
        all_product_additional_metadatas = AdditionalMetadata.objects.filter(
            related_courses__type__slug=product_type_slug_map[self.product_type],
            product_status='Published'
        ).values_list('external_identifier', flat=True)

        archived_products = set(all_product_additional_metadatas).difference(course_external_identifiers)
        archived_products_queryset = AdditionalMetadata.objects.filter(external_identifier__in=archived_products)
        archived_products_queryset.update(product_status="Archived")
        self.ingestion_summary['archived_products'] = list(archived_products)

        logger.info("Archived {} products in discovery.".format(len(archived_products)))  # lint-amnesty, pylint: disable=logging-format-interpolation
        logger.info("Archived Courses External Identifiers:")
        for archived_product in archived_products:
            logger.info(archived_product)

    def _update_course_api_request_data(self, data, course, is_draft):
        """
        Create and return the request data for making a patch call to update the course.
        """
        collaborator_uuids = self.process_collaborators(data.get('collaborators', ''), course.key)
        subjects = self.get_subject_slugs(
            data.get('primary_subject'),
            data.get('secondary_subject'),
            data.get('tertiary_subject')
        )

        update_course_data = {
            'draft': is_draft,
            'key': course.key,
            'uuid': str(course.uuid),
            'url_slug': data.get('slug') or course.active_url_slug,
            'type': str(course.type.uuid),
            'subjects': subjects,
            'collaborators': collaborator_uuids,
            'prices': self.get_pricing_representation(data['verified_price'], course.type),

            'title': data['title'],
            'syllabus_raw': data['syllabus'],
            'level_type': data['course_level'],
            'outcome': data['what_will_you_learn'],
            'faq': data.get('frequently_asked_questions', ''),
            'video': {'src': data.get('about_video_link', '')},
            'prerequisites_raw': data.get('prerequisites', ''),
            'full_description': data['long_description'],
            'short_description': data['short_description'],
            'additional_metadata': self.get_additional_metadata_dict(data, course.type.slug),
            'learner_testimonials': data.get('learner_testimonials', ''),
            'additional_information': data.get('additional_information', ''),
            'organization_short_code_override': data.get('organization_short_code_override', ''),
        }
        return update_course_data

    def _update_course_run_request_data(self, data, course_run, course_type, is_draft):
        """
        Create and return the request data for making a patch call to update the course run.
        """
        program_type = data.get('expected_program_type')
        staff_uuids = self.process_staff_names(data.get('staff', ''), course_run.key)
        content_language = self.verify_and_get_language_tags(data['content_language'])
        transcript_language = self.verify_and_get_language_tags(data['transcript_language'])

        update_course_run_data = {
            'run_type': str(course_run.type.uuid),
            'key': course_run.key,
            'prices': self.get_pricing_representation(data['verified_price'], course_type),
            'staff': staff_uuids,
            'draft': is_draft,

            'weeks_to_complete': data['length'],
            'min_effort': data['minimum_effort'],
            'max_effort': data['maximum_effort'],
            'content_language': content_language[0],
            'expected_program_name': data.get('expected_program_name', ''),
            'transcript_languages': transcript_language,
            'go_live_date': self.get_formatted_datetime_string(data['publish_date']),
            'expected_program_type': program_type if program_type in self.PROGRAM_TYPES else None,
            'upgrade_deadline_override': self.get_formatted_datetime_string(
                f"{data.get('upgrade_deadline_override_date', '')} "
                f"{data.get('upgrade_deadline_override_time', '')}".strip()
            ),
        }
        return update_course_run_data

    def get_formatted_datetime_string(self, date_string):
        """
        Return the datetime string into the desired format %Y-%m-%dT%H:%M:%SZ
        """
        return serialize_datetime(self.parse_date(date_string))

    def get_pacing_type(self, pacing):
        """
        Return appropriate pacing selection against a provided pacing string.
        """
        if pacing:
            pacing = pacing.lower()

        if pacing == 'instructor-paced':
            return CourseRunPacing.Instructor
        elif pacing == 'self-paced':
            return CourseRunPacing.Self
        else:
            return None

    def verify_and_get_language_tags(self, language_str):
        """
        Given a string of language tags or names, verify their existence in the database
        and return a list of language codes.
        """
        languages_codes_list = []
        languages_list = language_str.split(',')
        for language in languages_list:
            language = language.strip()
            language_obj = LanguageTag.objects.filter(
                Q(name=language) | Q(code=language)
            ).first()
            if not language_obj:
                raise Exception(
                    'Language {} from provided string {} is either missing or an invalid ietf language'.format(
                        language, language_str
                    )
                )
            languages_codes_list.append(language_obj.code)
        return languages_codes_list

    def _call_course_api(self, method, url, data):
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
            logger.info("API request failed for url {} with response: {}".format(url, response.content.decode('utf-8')))  # lint-amnesty, pylint: disable=logging-format-interpolation
        response.raise_for_status()
        return response

    def _create_course(self, data, course_type, course_run_type_uuid):
        """
        Make a course entry through course api.
        """
        course_api_url = reverse('api:v1:course-list')
        url = f"{settings.DISCOVERY_BASE_URL}{course_api_url}"

        request_data = self._create_course_api_request_data(data, course_type, course_run_type_uuid)
        response = self._call_course_api('POST', url, request_data)
        if response.status_code not in (200, 201):
            logger.info("Course creation response: {}".format(response.content))  # lint-amnesty, pylint: disable=logging-format-interpolation
        return response.json()

    def _update_course(self, data, course, is_draft):
        """
        Update the course data.
        """
        course_api_url = reverse('api:v1:course-detail', kwargs={'key': course.uuid})
        url = f"{settings.DISCOVERY_BASE_URL}{course_api_url}?exclude_utm=1"
        request_data = self._update_course_api_request_data(data, course, is_draft)
        response = self._call_course_api('PATCH', url, request_data)

        if response.status_code not in (200, 201):
            logger.info("Course update response: {}".format(response.content))  # lint-amnesty, pylint: disable=logging-format-interpolation
        return response.json()

    def _update_course_run(self, data, course_run, course_type, is_draft):
        """
        Update the course run data.
        """
        course_run_api_url = reverse('api:v1:course_run-detail', kwargs={'key': course_run.key})
        url = f"{settings.DISCOVERY_BASE_URL}{course_run_api_url}?exclude_utm=1"
        request_data = self._update_course_run_request_data(data, course_run, course_type, is_draft)
        response = self._call_course_api('PATCH', url, request_data)
        if response.status_code not in (200, 201):
            logger.info("Course run update response: {}".format(response.content))  # lint-amnesty, pylint: disable=logging-format-interpolation
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
            transformed_dict[updated_key] = value
        return transformed_dict

    def get_course_key(self, organization_key, number):
        """
        Given organization key and course number, return course key.
        """
        return '{org}+{number}'.format(org=organization_key, number=number)

    def get_pricing_representation(self, price, course_type):
        """
        Return dict representation of prices for a given course type.
        """
        prices = {}
        entitlement_types = course_type.entitlement_types.all()
        for entitlement_type in entitlement_types:
            prices.update({entitlement_type.slug: price})
        return prices

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
                logger.exception("Unable to locate subject {} in the database. Skipping subject association".format(  # lint-amnesty, pylint: disable=logging-format-interpolation
                    subject
                ))
                raise

        return subject_slugs

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
                logger.info("Collaborator {} created for course {}".format(collaborator, course_key))  # lint-amnesty, pylint: disable=logging-format-interpolation
        return collaborator_uuids

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
                logger.info("Staff with name {} has been created for course run {}".format(  # lint-amnesty, pylint: disable=logging-format-interpolation
                    staff_name,
                    course_run_key
                ))
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
        stats = []
        stat1_dict = self.process_heading_blurb(stat1, stat1_text)
        stat2_dict = self.process_heading_blurb(stat2, stat2_text)

        if stat1_dict:
            stats.append(stat1_dict)
        if stat2_dict:
            stats.append(stat2_dict)
        return stats

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

    def get_additional_metadata_dict(self, data, type_slug):
        """
        Return the appropriate additional metadata dict representation, skipping the keys that are not
        present in the input data dict.
        """
        if type_slug not in [CourseType.EXECUTIVE_EDUCATION_2U, CourseType.BOOTCAMP_2U]:
            return {}

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
                data['meta_title'],
                data['meta_description'],
                data['meta_keywords']
            )})
        return additional_metadata
