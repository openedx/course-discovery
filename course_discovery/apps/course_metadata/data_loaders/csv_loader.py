"""
Data loader responsible for creating course and course runs entries in discovery Database,
creating and updating related objects in Studio, and ecommerce, provided a csv containing the required information.
"""
import csv
import logging

from django.conf import settings
from django.db.models import Q
from django.urls import reverse

from course_discovery.apps.core.utils import serialize_datetime
from course_discovery.apps.course_metadata.data_loaders import AbstractDataLoader
from course_discovery.apps.course_metadata.models import (
    Collaborator, Course, CourseRun, CourseRunPacing, CourseRunType, CourseType, Organization, Person, ProgramType
)
from course_discovery.apps.course_metadata.utils import download_and_save_course_image
from course_discovery.apps.ietf_language_tags.models import LanguageTag

logger = logging.getLogger(__name__)


class CSVDataLoader(AbstractDataLoader):
    PROGRAM_TYPES = [
        ProgramType.XSERIES,
        ProgramType.MASTERS,
        ProgramType.MICROMASTERS,
        ProgramType.MICROBACHELORS,
        ProgramType.PROFESSIONAL_PROGRAM_WL,
        ProgramType.PROFESSIONAL_CERTIFICATE
    ]

    def __init__(self, partner, api_url=None, max_workers=None, is_threadsafe=False, csv_path=None):
        super().__init__(partner, api_url, max_workers, is_threadsafe)

        try:
            self.reader = csv.DictReader(open(csv_path, 'r'))
        except FileNotFoundError:
            logger.exception("Error opening csv file at path {}".format(csv_path))
            raise  # re-raising exception to avoid moving the code flow

    def ingest(self):  # pylint: disable=too-many-statements
        logger.info("Initiating CSV data loader flow.")
        for row in self.reader:

            row = self.transform_dict_keys(row)
            course_title = row['title']
            org_key = row['organization']

            logger.info('Starting data import flow for {}'.format(course_title))
            if not Organization.objects.filter(key=org_key).exists():
                logger.error("Organization {} does not exist in database. Skipping CSV loader for course {}".format(
                    org_key,
                    course_title
                ))
                continue

            try:
                course_type = CourseType.objects.get(name=row['course_enrollment_track'])
                course_run_type = CourseRunType.objects.get(name=row['course_run_enrollment_track'])
            except CourseType.DoesNotExist:
                logger.exception("CourseType {} does not exist in the database.".format(
                    row['course_enrollment_track']
                ))
                continue
            except CourseRunType.DoesNotExist:
                logger.exception("CourseRunType {} does not exist in the database.".format(
                    row['course_run_enrollment_track']
                ))
                continue

            course_key = self.get_course_key(org_key, row['number'])

            course = Course.objects.filter_drafts(key=course_key, partner=self.partner).first()
            if course:
                course_run = CourseRun.objects.filter_drafts(course=course).first()
                logger.info("Course {} is located in the database.".format(course_key))
            else:
                logger.info("Course key {} could not be found in database, creating the course.".format(course_key))
                try:
                    _ = self._create_course(row, course_type, course_run_type.uuid)
                except Exception:  # pylint: disable=broad-except
                    logger.exception("Error occurred when attempting to create a new course against key {}".format(
                        course_key
                    ))
                    continue
                course = Course.everything.get(key=course_key, partner=self.partner)
                course_run = CourseRun.everything.filter(course=course).first()

            is_downloaded = download_and_save_course_image(course, row['image'])
            if not is_downloaded:
                logger.error("Unexpected error happened while downloading image for course {}".format(
                    course_key
                ))
                continue

            try:
                self._update_course(row, course)
            except Exception:  # pylint: disable=broad-except
                logger.exception("An unknown error occurred while updating course information")
                continue

            # No need to update the course run if the run is already in the review
            if not course_run.in_review:
                try:
                    self._update_course_run(row, course_run, course_type)
                    course_run.refresh_from_db()
                except Exception:  # pylint: disable=broad-except
                    logger.exception("An unknown error occurred while updating course run information")
                    continue

            try:
                self._complete_run_review(row, course_run)
            except Exception:  # pylint: disable=broad-except
                logger.exception("An unknown error occurred while completing course run review")

            logger.info("Course and course run updated successfully for course key {}".format(course_key))
        logger.info("CSV loader ingest pipeline has completed.")

    def _create_course_api_request_data(self, data, course_type, course_run_type_uuid):
        """
        Given a data dictionary, return a reduced data representation in dict
        which will be used as input for course creation via course api.
        """
        pricing = self.get_pricing_representation(data['verified_price'], course_type)

        # TODO: make appropriate timezone adjustment when it is confirmed if time values are in EST or UTC
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

    def _update_course_api_request_data(self, data, course):
        """
        Create and return the request data for making a patch call to update the course.
        """
        collaborator_uuids = self.process_collaborators(data['collaborators'], course.key)
        subjects = self.get_subject_slugs(
            data.get('primary_subject'),
            data.get('secondary_subject'),
            data.get('tertiary_subject')
        )

        update_course_data = {
            'draft': False,
            'key': course.key,
            'uuid': str(course.uuid),
            'url_slug': course.url_slug,
            'type': str(course.type.uuid),
            'subjects': subjects,
            'collaborators': collaborator_uuids,
            'prices': self.get_pricing_representation(data['verified_price'], course.type),

            'title': data['title'],
            'syllabus_raw': data['syllabus'],
            'level_type': data['course_level'],
            'outcome': data['what_will_you_learn'],
            'faq': data['frequently_asked_questions'],
            'video': {'src': data['about_video_link']},
            'prerequisites_raw': data['prerequisites'],
            'full_description': data['long_description'],
            'short_description': data['short_description'],
            'learner_testimonials': data['learner_testimonials'],
            'additional_information': data['additional_information'],
            'additional_metadata': {'external_url': data['redirect_url']},
        }
        return update_course_data

    def _update_course_run_request_data(self, data, course_run, course_type):
        """
        Create and return the request data for making a patch call to update the course run.
        """
        program_type = data['expected_program_type']
        staff_uuids = self.process_staff_names(data['staff'], course_run.key)
        content_language = self.verify_and_get_language_tags(data['content_language'])
        transcript_language = self.verify_and_get_language_tags(data['transcript_language'])

        update_course_run_data = {
            'run_type': str(course_run.type.uuid),
            'key': course_run.key,
            'prices': self.get_pricing_representation(data['verified_price'], course_type),
            'staff': staff_uuids,
            'draft': False,

            'weeks_to_complete': data['length'],
            'min_effort': data['minimum_effort'],
            'max_effort': data['maximum_effort'],
            'content_language': content_language[0],
            'expected_program_name': data['expected_program_name'],
            'transcript_languages': transcript_language,
            'go_live_date': self.get_formatted_datetime_string(data['publish_date']),
            'expected_program_type': program_type if program_type in self.PROGRAM_TYPES else None,
            'upgrade_deadline_override': self.get_formatted_datetime_string(
                f"{data['upgrade_deadline_override_date']} {data['upgrade_deadline_override_time']}"
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
            logger.info("Course creation response: {}".format(response.content))
        return response.json()

    def _update_course(self, data, course):
        """
        Update the course data.
        """
        course_api_url = reverse('api:v1:course-detail', kwargs={'key': course.uuid})
        url = f"{settings.DISCOVERY_BASE_URL}{course_api_url}?exclude_utm=1"
        request_data = self._update_course_api_request_data(data, course)
        response = self._call_course_api('PATCH', url, request_data)

        if response.status_code not in (200, 201):
            logger.info("Course update response: {}".format(response.content))
        return response.json()

    def _update_course_run(self, data, course_run, course_type):
        """
        Update the course run data.
        """
        course_run_api_url = reverse('api:v1:course_run-detail', kwargs={'key': course_run.key})
        url = f"{settings.DISCOVERY_BASE_URL}{course_run_api_url}?exclude_utm=1"
        request_data = self._update_course_run_request_data(data, course_run, course_type)
        response = self._call_course_api('PATCH', url, request_data)
        if response.status_code not in (200, 201):
            logger.info("Course run update response: {}".format(response.content))
        return response.json()

    def _complete_run_review(self, data, course_run):
        """
        Complete the review phase of the course run and publish(internally by model save) if applicable.
        """
        has_ofac_restrictions = data['course_embargo_(ofac)_restriction_text_added_to_the_faq_section'].lower() in [
            'yes', '1', 'true'
        ]
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
        subjects = [subject.lower().replace(' ', '-') for subject in subjects if subject]
        return list(set(subjects))

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
                logger.info("Collaborator {} created for course {}".format(collaborator, course_key))
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
                logger.info("Staff with name {} has been created for course run {}".format(
                    staff_name,
                    course_run_key
                ))
        return staff_uuids
