"""
Data loader responsible for creating degree entries in discovery Database,
"""
import csv
import logging

from course_discovery.apps.course_metadata.data_loaders import AbstractDataLoader
from course_discovery.apps.course_metadata.models import (
    Curriculum, Degree, DegreeAdditionalMetadata, LanguageTag, LevelType, Organization, Program, ProgramType,
    Specialization, Subject
)
from course_discovery.apps.course_metadata.utils import download_and_save_program_image

logger = logging.getLogger(__name__)


class DegreeCSVDataLoader(AbstractDataLoader):
    """ Loads the degrees from the csv file """

    DEGREE_REQUIRED_DATA_FIELDS = [
        'title', 'card_image_url', 'product_type', 'organization_key', 'organization_short_code_override',
        'slug', 'primary_subject', 'content_language', 'course_level', 'paid_landing_page_url', 'organic_url',
        'identifier',
        'overview', 'courses',
    ]

    def __init__(self, partner, api_url=None, max_workers=None, is_threadsafe=False, csv_path=None):
        super().__init__(partner, api_url, max_workers, is_threadsafe)

        self.messages_list = []  # to show failure/skipped ingestion message at the end
        self.degree_uuids = {}  # to show the discovery degrees/program ids for each processed degree
        try:
            self.reader = csv.DictReader(open(csv_path, 'r'))  # lint-amnesty, pylint: disable=consider-using-with
        except FileNotFoundError:
            logger.exception("Error opening csv file at path {}".format(csv_path))    # lint-amnesty, pylint: disable=logging-format-interpolation
            raise  # re-raising exception to avoid moving the code flow

    def ingest(self):
        logger.info("Initiating Degree CSV data loader flow.")
        for row in self.reader:
            row = self.transform_dict_keys(row)

            degree_slug = row['slug']
            program_type = row['product_type'].replace('\'', '').lower()

            message = self.validate_degree_data(row)
            if message:
                logger.error("Data validation issue for degree {}, skipping ingestion".format(degree_slug))    # lint-amnesty, pylint: disable=logging-format-interpolation
                self.messages_list.append("[DATA VALIDATION ERROR] Degree {}. Missing data: {}".format(
                    degree_slug, message
                ))
                continue

            logger.info('Starting data import flow for {}'.format(degree_slug))    # lint-amnesty, pylint: disable=logging-format-interpolation

            org = self._get_object(Organization, "key", row['organization_key'], degree_slug)
            program_type = self._get_object(ProgramType, "slug", program_type, degree_slug)
            primary_subject_override = self._get_object(
                Subject, "translations__name",
                row['primary_subject'], degree_slug
            )
            level_type_override = self._get_object(
                LevelType, "translations__name_t",
                row['course_level'], degree_slug
            )
            language_override = self._get_object(
                LanguageTag, "name",
                row['content_language'], degree_slug
            )

            if not (org and program_type and primary_subject_override and level_type_override and language_override):
                continue

            # get degree object from slug and external_identifier
            degree = Degree.objects.filter(
                marketing_slug=degree_slug, partner=self.partner,
                additional_metadata__external_identifier=row['identifier']
            ).first()

            logger.info("Degree {} {} located in the database. {} degree.".format(   # lint-amnesty, pylint: disable=logging-format-interpolation
                degree_slug,
                "is" if degree else "is not",
                "Creating new" if not degree else "Updating existing"
            ))

            try:
                degree = self._update_or_create_degree(
                    row, program_type, primary_subject_override,
                    level_type_override, language_override
                )
            # we can get the IntegrityError if the degree already exists in the database
            # or any related error while updating or creating degree object
            except Exception:   # pylint: disable=broad-except
                logger.exception("An unknown error occurred while {} degree information".format(  # lint-amnesty, pylint: disable=logging-format-interpolation
                    "updating" if degree else "creating"
                ))
                self.messages_list.append('[DEGREE {} ERROR] degree {}'.format(
                    "UPDATE" if degree else "CREATE",
                    degree_slug
                ))
                continue

            self._handle_organization_data(org, degree)
            self._handle_additional_metadata(row, degree)
            self._handle_image_fields(row, degree)
            self._handle_specializations(row, degree)
            self._handle_courses(row, degree)

            logger.info("Degree updated successfully for degree key {}".format(degree.uuid))    # lint-amnesty, pylint: disable=logging-format-interpolation
            self.degree_uuids[str(degree.uuid)] = degree.marketing_slug

        logger.info("Degree CSV loader ingest pipeline has completed.")

        # Log the summarized errors at the end for easy filtering of the degrees whose ingestion failed
        if self.messages_list:
            logger.info("Summarized errors:")
            for msg in self.messages_list:
                logger.error(msg)

        # log the processed degree uuids and their marketing_slugs
        if self.degree_uuids:
            logger.info("Degree UUIDs:")
            for degree_uuid, marketing_slug in self.degree_uuids.items():
                logger.info("{}:{}".format(degree_uuid, marketing_slug))    # lint-amnesty, pylint: disable=logging-format-interpolation

    def validate_degree_data(self, data):
        """
        Verify the required data key-values for a program type are present in the provided
        data dictionary and return a comma separated string of missing data fields.
        """
        missing_fields = []

        for field in self.DEGREE_REQUIRED_DATA_FIELDS:
            if not (field in data and data[field]):
                missing_fields.append(field)

        if missing_fields:
            return ', '.join(missing_fields)
        return ''

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

    def _update_or_create_degree(
        self, data, program_type, primary_subject_override,
        level_type_override, language_override
    ):
        """
        Create or Update a degree object through ORM
        """
        data_dict = {
            "type": program_type,
            "primary_subject_override": primary_subject_override,
            "level_type_override": level_type_override,
            "language_override": language_override,
            "title": data['title'],
            "overview": data['overview'],
            "organization_short_code_override": data.get('organization_short_code_override', ''),
            "partner": self.partner,

        }
        degree, created = Degree.objects.update_or_create(
            marketing_slug=data['slug'],
            additional_metadata__external_identifier=data['identifier'],
            defaults=data_dict
        )

        logger.info("Degree with slug {} is {}".format(    # lint-amnesty, pylint: disable=logging-format-interpolation
            degree.marketing_slug,
            "created" if created else "updated",
        ))

        return degree

    def _handle_organization_data(self, org, degree):
        """
        Handle organization data for a degree.
        """
        degree.authoring_organizations.clear()
        degree.authoring_organizations.add(org)

    def _handle_image_fields(self, data, degree):
        """
        Handle the image fields for the degree
        """

        program = Program.objects.get(degree=degree, partner=self.partner)
        is_downloaded = download_and_save_program_image(
            program, data['card_image_url'],
        )
        if not is_downloaded:
            logger.error("Unexpected error happened while downloading image for degree {}".format(  # lint-amnesty, pylint: disable=logging-format-interpolation
                degree.marketing_slug
            ))
            self.messages_list.append('[DEGREE IMAGE DOWNLOAD FAILURE] degree {}'.format(degree.marketing_slug))

        if data.get('organization_logo_override'):
            is_downloaded = download_and_save_program_image(
                program, data['organization_logo_override'],
                'organization_logo_override',
            )
            if not is_downloaded:
                logger.error("Unexpected error happened while downloading org logo image for degree {}".format(  # lint-amnesty, pylint: disable=logging-format-interpolation
                    degree.marketing_slug
                ))
                self.messages_list.append('[ORG LOGO OVERRIDE IMAGE DOWNLOAD FAILURE] degree {}'.format(  # lint-amnesty, pylint: disable=logging-format-interpolation
                    degree.marketing_slug
                ))

    def _handle_courses(self, data, degree):
        """
        Handle the courses for the degree
        """
        delimeter = '|'
        courses_data = data.get('courses', '')
        if courses_data:
            courses = courses_data.split(delimeter)
            html_list = [f"<li>{course.strip()}</li>" for course in courses]
            marketing_text = '<ul>{}</ul>'.format("".join(html_list))

            program = Program.objects.get(degree=degree, partner=self.partner)
            curriculum, created = Curriculum.objects.update_or_create(
                program=program,
                defaults={
                    'marketing_text': marketing_text,
                }
            )

            logger.info("Curriculum {} is {} for Degree slug {}".format(    # lint-amnesty, pylint: disable=logging-format-interpolation
                curriculum,
                "created" if created else "updated",
                degree.marketing_slug,
            ))

    def _handle_specializations(self, data, degree):
        """
        Handle the specialization fields for the degree
        """
        specializations_data = data.get('specializations', '')
        if specializations_data:
            degree.specializations.clear()
            specializations_data = specializations_data.split('|')
            for specialization in specializations_data:
                specialization = specialization.strip()
                if specialization:
                    specialization_obj, _ = Specialization.objects.get_or_create(value=specialization)
                    degree.specializations.add(specialization_obj)

    def _get_object(self, model, key, value, degree_slug):
        """
        Get an object from the database by its key and value
        """
        model_name = model._meta.object_name
        kwrags = {key: value}
        # for translatable models, we need to pass the language code
        if model_name in ['Subject', 'LevelType']:
            kwrags['translations__language_code'] = 'en'
        try:
            obj = model.objects.get(**kwrags)
            return obj
        except model.DoesNotExist:
            logger.exception("{} {} does not exist. Skipping CSV loader for degree {}".format(   # lint-amnesty, pylint: disable=logging-format-interpolation
                model_name,
                value,
                degree_slug
            ))
            self.messages_list.append('[MISSING {}] {}: {}, degree: {}'.format(
                model_name.upper(), model_name, value, degree_slug
            ))
            return None

    def _handle_additional_metadata(self, data, degree):
        """
        Make a degree additional metadata object through ORM
        """
        additional_metadata_dict = {
            "external_identifier": data['identifier'],
            "organic_url": data['organic_url'],
            "external_url": data['paid_landing_page_url'],
        }

        additional_metadata, created = DegreeAdditionalMetadata.objects.update_or_create(
            degree=degree,
            defaults=additional_metadata_dict
        )

        logger.info("AdditionalMetadata {} is {} with Degree slug {}".format(    # lint-amnesty, pylint: disable=logging-format-interpolation
            additional_metadata,
            "created" if created else "updated",
            degree.marketing_slug,
        ))
