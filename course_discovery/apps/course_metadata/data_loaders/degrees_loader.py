"""
Data loader responsible for creating degree entries in discovery Database,
"""
import csv
import logging

from course_discovery.apps.course_metadata.choices import ProgramStatus
from course_discovery.apps.course_metadata.data_loaders import AbstractDataLoader
from course_discovery.apps.course_metadata.models import (
    Curriculum, Degree, DegreeAdditionalMetadata, Organization, Program, ProgramType, Specialization
)
from course_discovery.apps.course_metadata.utils import download_and_save_program_image

logger = logging.getLogger(__name__)


class DegreeCSVDataLoader(AbstractDataLoader):

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
            # TODO: test and decide if need to make transaction atomic
            # with transaction.atomic():

            row = self.transform_dict_keys(row)
            degree_title = row['title']

            logger.info('Starting data import flow for {}'.format(degree_title))    # lint-amnesty, pylint: disable=logging-format-interpolation

            org = self._get_object(Organization, "key", row['organization_key'], degree_title)
            program_type = self._get_object(ProgramType, "slug", row['product_type'], degree_title)
            # primary_subject_override = self._get_object(
            #     Subjetcs, "translations__name",
            #     row['primary_subject_override'], degree_title
            # )
            # level_type_override = self._get_object(
            #     LevelType, "name_t",
            #     row['level_type_override'], degree_title
            # )
            # language_override = self._get_object(
            #     LanguageTag, "code",
            #     row['language_override'], degree_title
            # )

            if not org or not program_type:
                continue

            message = self.validate_degree_data(program_type, row)
            if message:
                logger.error("Data validation issue for degree {}, skipping ingestion".format(degree_title))    # lint-amnesty, pylint: disable=logging-format-interpolation
                self.messages_list.append("[DATA VALIDATION ERROR] Degree {}. Missing data: {}".format(
                    degree_title, message
                ))
                continue

            # get degree object from title and external_identifier
            degree = Degree.objects.filter(
                title=degree_title, partner=self.partner,
                # additional_metadata__external_identifier=row['identifier']
            ).first()

            # temp check to prevent existing degree/programs from being overwritten
            additioanl_metadata = DegreeAdditionalMetadata.objects.filter(degree=degree).first()
            if degree and (not additioanl_metadata or additioanl_metadata.external_identifier != row['identifier']):
                logger.error("Degree {} already exists, but external identifier didn't match. Skipping".format(   # lint-amnesty, pylint: disable=logging-format-interpolation
                    degree_title
                ))
                self.messages_list.append('[DEGREE UPDATE ERROR] degree {}'.format(
                    degree_title
                ))
                continue

            logger.info("Degree {} {} located in the database. {} degree.".format(   # lint-amnesty, pylint: disable=logging-format-interpolation
                degree_title,
                "is" if degree else "is not",
                "Creating new" if not degree else "Updating existing"
            ))

            try:
                degree = self._update_or_create_degree(row, program_type)
            except Exception:   # pylint: disable=broad-except
                logger.exception("An unknown error occurred while {} degree information".format(  # lint-amnesty, pylint: disable=logging-format-interpolation
                    "updating" if degree else "creating"
                ))
                self.messages_list.append('[DEGREE {} ERROR] degree {}'.format(
                    "UPDATE" if degree else "CREATE",
                    degree_title
                ))
                continue

            # degree.authoring_organizations.clear()
            degree.authoring_organizations.add(org)

            self._handle_additional_metadata(row, degree)
            self._handle_image_fields(row, degree)
            self._handle_specializations(row, degree)
            self._handle_courses(row, degree)
            # TODO: handle curricula

            logger.info("Degree updated successfully for degree key {}".format(degree.uuid))    # lint-amnesty, pylint: disable=logging-format-interpolation
            self.degree_uuids[str(degree.uuid)] = degree.title

        logger.info("Degree CSV loader ingest pipeline has completed.")

        # Log the summarized errors at the end for easy filtering of the degrees whose ingestion failed
        if self.messages_list:
            logger.info("Summarized errors:")
            for msg in self.messages_list:
                logger.error(msg)

        # log the processed degree uuids and their titles
        if self.degree_uuids:
            logger.info("Degree UUIDs:")
            for degree_uuid, title in self.degree_uuids.items():
                logger.info("{}:{}".format(degree_uuid, title))    # lint-amnesty, pylint: disable=logging-format-interpolation

    def validate_degree_data(self, program_type, data):  # pylint: disable=unused-argument
        """
        Verify the required data key-values for a program type are present in the provided
        data dictionary and return a comma separated string of missing data fields.
        """
        # TODO
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

    def _update_or_create_degree(self, data, program_type):
        """
        Make a degree object through ORM
        """
        data_dict = {
            "type": program_type,
            "status": ProgramStatus.Unpublished,
            # "primary_subject_override":  primary_subject_override,
            # "level_type_override": level_type_override,
            # "language_override": language_override,
            "marketing_slug": data['slug'],
            "overview": data['overview'],
            # "organization_short_code_override": data.get('organization_short_code_override', ''),
            "partner": self.partner,

        }
        # TODO: handle exceptions
        degree, updated = Degree.objects.update_or_create(
            title=data['title'],
            # additional_metadata__external_identifier=data['identifier'],
            defaults=data_dict
        )

        logger.info("Degree with title {} is {}".format(    # lint-amnesty, pylint: disable=logging-format-interpolation
            degree,
            "updated" if updated else "created",
        ))

        return degree

    def _handle_image_fields(self, data, degree):
        """
        Handle the image fields for the degree
        """

        program = Program.objects.get(degree=degree, partner=self.partner)
        is_downloaded = download_and_save_program_image(program, data['card_image_url'])
        if not is_downloaded:
            logger.error("Unexpected error happened while downloading image for degree {}".format(  # lint-amnesty, pylint: disable=logging-format-interpolation
                degree.title
            ))
            self.messages_list.append('[IMAGE DOWNLOAD FAILURE] degree {}'.format(degree.title))

        if data.get('organization_logo_override'):
            is_downloaded = download_and_save_program_image(
                program, data['organization_logo_override'],
                'organization_logo_override'
            )
            if not is_downloaded:
                logger.error("Unexpected error happened while downloading image for degree {}".format(  # lint-amnesty, pylint: disable=logging-format-interpolation
                    degree.title
                ))
                self.messages_list.append('[IMAGE DOWNLOAD FAILURE] degree {}'.format(degree.title))

    def _handle_courses(self, data, degree):
        """
        Handle the courses for the degree
        """
        delimeter = '|'
        courses_data = data.get('courses', '')
        if courses_data:
            courses = courses_data.split(delimeter)
            marketing_text = [course.strip() for course in courses]
            marketing_text = "\n".join(marketing_text)

            program = Program.objects.get(degree=degree, partner=self.partner)
            curriculam, created = Curriculum.objects.update_or_create(
                program=program,
                defaults={
                    'marketing_text': marketing_text,
                }
            )

            logger.info("Curriculam {} is {} with Degree title {}".format(    # lint-amnesty, pylint: disable=logging-format-interpolation
                curriculam,
                "created" if created else "updated",
                degree,
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

    def _get_object(self, model, key, value, degree_title):
        """
        Get an object from the database by its key and value
        """
        model_name = model._meta.object_name
        try:
            obj = model.objects.get(**{key: value})
            return obj
        except model.DoesNotExist:
            logger.exception("{} {} does not exist. Skipping CSV loader for degree {}".format(   # lint-amnesty, pylint: disable=logging-format-interpolation
                model_name,
                value,
                degree_title
            ))
            self.messages_list.append('[MISSING {}] {}: {}, degree: {}'.format(
                model_name.upper(), model_name, value, degree_title
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

        logger.info("AdditionalMetdata {} is {} with Degree title {}".format(    # lint-amnesty, pylint: disable=logging-format-interpolation
            additional_metadata,
            "created" if created else "updated",
            degree,
        ))
