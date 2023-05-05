"""
Data loader responsible for creating degree entries in discovery Database,
"""
import csv
import logging

import unicodecsv
from django.conf import settings

from course_discovery.apps.course_metadata.data_loaders import AbstractDataLoader
from course_discovery.apps.course_metadata.data_loaders.constants import (
    DEGREE_LOADER_ERROR_LOG_SEQUENCE, DegreeCSVIngestionErrorMessages, DegreeCSVIngestionErrors
)
from course_discovery.apps.course_metadata.data_loaders.utils import map_external_org_code_to_internal_org_code
from course_discovery.apps.course_metadata.gspread_client import GspreadClient
from course_discovery.apps.course_metadata.models import (
    Curriculum, Degree, DegreeAdditionalMetadata, LanguageTag, LevelType, Organization, Program, ProgramType, Source,
    Specialization, Subject
)
from course_discovery.apps.course_metadata.utils import download_and_save_program_image

logger = logging.getLogger(__name__)


class DegreeCSVDataLoader(AbstractDataLoader):
    """ Loads the degrees from the csv file """

    DEGREE_REQUIRED_FIELDS = [
        'title', 'card_image_url', 'product_type', 'organization_key', 'organization_short_code_override',
        'slug', 'primary_subject', 'content_language', 'course_level', 'paid_landing_page_url', 'organic_url',
        'identifier', 'overview',
    ]

    # Define the error type and error messages for various required data models for Degree ingestion
    MODEL_ERROR_MAPPING = {
        Organization: {
            'error_type': DegreeCSVIngestionErrors.MISSING_ORGANIZATION,
            'error_message': DegreeCSVIngestionErrorMessages.MISSING_ORGANIZATION,
        },
        ProgramType: {
            'error_type': DegreeCSVIngestionErrors.MISSING_PROGRAM_TYPE,
            'error_message': DegreeCSVIngestionErrorMessages.MISSING_PROGRAM_TYPE,
        },
        Subject: {
            'error_type': DegreeCSVIngestionErrors.MISSING_SUBJECT_DATA,
            'error_message': DegreeCSVIngestionErrorMessages.MISSING_SUBJECT_DATA,
        },
        LevelType: {
            'error_type': DegreeCSVIngestionErrors.MISSING_LEVEL_TYPE_DATA,
            'error_message': DegreeCSVIngestionErrorMessages.MISSING_LEVEL_TYPE_DATA,
        },
        LanguageTag: {
            'error_type': DegreeCSVIngestionErrors.MISSING_LANGUAGE_TAG_DATA,
            'error_message': DegreeCSVIngestionErrorMessages.MISSING_LANGUAGE_TAG_DATA,
        }
    }

    def __init__(
        self, partner, api_url=None, max_workers=None, is_threadsafe=False,
        csv_path=None, csv_file=None, args_from_env=None, product_type=None, product_source='edx'
    ):
        super().__init__(partner, api_url, max_workers, is_threadsafe)

        self.error_logs = {}
        self.degree_uuids = {}  # to show the discovery degrees/program ids for each processed degree
        self.ingestion_summary = {
            'total_products_count': 0,
            'success_count': 0,
            'failure_count': 0,
            'updated_products_count': 0,
            'created_products': [],
        }

        try:
            self.product_source = Source.objects.get(slug=product_source)
        except Source.DoesNotExist:
            logger.exception(f"Unable to locate source with slug {product_source}")
            raise

        for error_log_key in DEGREE_LOADER_ERROR_LOG_SEQUENCE:
            self.error_logs.setdefault(error_log_key, [])

        try:
            if args_from_env:
                # TODO: add unit tests
                product_type_config = settings.PRODUCT_METADATA_MAPPING[product_type][self.product_source.slug]
                gspread_client = GspreadClient()
                self.reader = gspread_client.read_data(product_type_config)
            else:
                # Read file from the path if given. Otherwise,
                # read from the file received from DegreeDataLoaderConfiguration.
                self.reader = csv.DictReader(open(csv_path, 'r')) if csv_path \
                    else list(unicodecsv.DictReader(csv_file))  # lint-amnesty, pylint: disable=consider-using-with
        except FileNotFoundError:
            logger.exception("Error opening csv file at path {}".format(csv_path))    # lint-amnesty, pylint: disable=logging-format-interpolation
            raise  # re-raising exception to avoid moving the code flow
        except Exception:
            logger.exception("Error reading the input data source")
            raise  # re-raising exception to avoid moving the code flow
        self.reader = list(self.reader)
        self.ingestion_summary['total_products_count'] = len(self.reader)

    def ingest(self):
        logger.info("Initiating Degree CSV data loader flow.")
        for row in self.reader:
            row = self.transform_dict_keys(row)

            degree_slug = row['slug']
            program_type = row['product_type'].replace('\'', '').lower()

            missing_data = self.validate_degree_data(row)
            if missing_data:
                error_message = DegreeCSVIngestionErrorMessages.MISSING_REQUIRED_DATA.format(
                    degree_slug=degree_slug,
                    missing_data=missing_data
                )
                logger.error(error_message)
                self._register_ingestion_error(DegreeCSVIngestionErrors.MISSING_REQUIRED_DATA, error_message)
                continue

            logger.info('Starting data import flow for {}'.format(degree_slug))    # lint-amnesty, pylint: disable=logging-format-interpolation

            org_key = map_external_org_code_to_internal_org_code(row['organization_key'], self.product_source.slug)
            org = self._get_object(Organization, "key", org_key, degree_slug)
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

            # get degree object from external_identifier and product source
            degree = Degree.objects.filter(
                partner=self.partner,
                additional_metadata__external_identifier=row['identifier'],
                product_source=self.product_source
            ).first()

            logger.info("Degree with external identifier {} {} located in the database. {} degree.".format(   # lint-amnesty, pylint: disable=logging-format-interpolation
                row['identifier'],
                "is" if degree else "is not",
                "Creating new" if not degree else "Updating existing"
            ))

            try:
                degree, is_degree_created = self._update_or_create_degree(
                    row, program_type, primary_subject_override,
                    level_type_override, language_override
                )
            # we can get the IntegrityError if the degree already exists in the database
            # or any related error while updating or creating degree object
            except Exception as exc:   # pylint: disable=broad-except
                error_type = DegreeCSVIngestionErrors.DEGREE_UPDATE_ERROR if degree else \
                    DegreeCSVIngestionErrors.DEGREE_CREATE_ERROR
                error_message = DegreeCSVIngestionErrorMessages.DEGREE_UPDATE_ERROR if degree else \
                    DegreeCSVIngestionErrorMessages.DEGREE_CREATE_ERROR
                error_message = error_message.format(
                    degree_slug=degree_slug,
                    exception_message=exc
                )
                logger.exception(error_message)
                self._register_ingestion_error(error_type, error_message)
                continue

            self._handle_organization_data(org, degree)
            self._handle_additional_metadata(row, degree)
            self._handle_image_fields(row, degree)
            self._handle_specializations(row, degree)
            self._handle_courses(row, degree)

            logger.info("Degree updated successfully for degree key {}".format(degree.uuid))    # lint-amnesty, pylint: disable=logging-format-interpolation
            self.degree_uuids[str(degree.uuid)] = degree.marketing_slug
            self._register_successful_ingestion(str(degree.uuid), is_degree_created)

        logger.info("Degree CSV loader ingest pipeline has completed.")

        self._render_error_logs()
        self._render_degree_uuids()

    def validate_degree_data(self, data):
        """
        Verify the required data key-values for a program type are present in the provided
        data dictionary and return a comma separated string of missing data fields.
        """
        missing_fields = []
        degree_variants = settings.DEGREE_VARIANTS_FIELD_MAP.copy()
        source_fields = self.DEGREE_REQUIRED_FIELDS + degree_variants.get(self.product_source.slug, [])
        for field in source_fields:
            if not (field in data and data[field]):
                missing_fields.append(field)

        if missing_fields:
            return ', '.join(missing_fields)
        return ''

    def _render_error_logs(self):
        if any(list(self.error_logs.values())):
            logger.info("Summarized errors:")
            for error_key in DEGREE_LOADER_ERROR_LOG_SEQUENCE:
                for msg in self.error_logs[error_key]:
                    logger.error(msg)
        else:
            logger.info("No errors reported in the ingestion")

    def _render_degree_uuids(self):
        # log the processed degree uuids and their marketing_slugs
        if self.degree_uuids:
            logger.info("Degree UUIDs:")
            for degree_uuid, marketing_slug in self.degree_uuids.items():
                logger.info("{}:{}".format(degree_uuid, marketing_slug))  # lint-amnesty, pylint: disable=logging-format-interpolation

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
            'errors': self.error_logs
        }

    def _register_successful_ingestion(self, program_uuid, created):
        """
        Register the summary of a successful ingestion.
        """
        self.ingestion_summary['success_count'] += 1
        if created:
            self.ingestion_summary['created_products'].append({
                'uuid': program_uuid
            })
        else:
            self.ingestion_summary['updated_products_count'] += 1

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
            "product_source": self.product_source,
            "marketing_slug": data['slug'],
        }

        degree, created = Degree.objects.update_or_create(
            additional_metadata__external_identifier=data['identifier'],
            defaults=data_dict
        )

        if degree.product_source and \
                degree.product_source.ofac_restricted_program_types.filter(id=program_type.id).exists():
            degree.mark_ofac_restricted()

        logger.info("Degree with slug {} is {}".format(    # lint-amnesty, pylint: disable=logging-format-interpolation
            degree.marketing_slug,
            "created" if created else "updated",
        ))

        return degree, created

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
            # TODO: Temporary addition of User agent to allow access to data CDNs
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                              '(KHTML, like Gecko) Chrome/101.0.4951.64 Safari/537.36'
            }
        )
        if not is_downloaded:
            error_message = DegreeCSVIngestionErrorMessages.IMAGE_DOWNLOAD_FAILURE.format(
                degree_slug=degree.marketing_slug
            )
            logger.error(error_message)
            self._register_ingestion_error(DegreeCSVIngestionErrors.IMAGE_DOWNLOAD_FAILURE, error_message)

        if data.get('organization_logo_override'):
            is_downloaded = download_and_save_program_image(
                program, data['organization_logo_override'],
                'organization_logo_override',
                # TODO: Temporary addition of User agent to allow access to data CDNs
                headers={
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                                  '(KHTML, like Gecko) Chrome/101.0.4951.64 Safari/537.36'
                }
            )
            if not is_downloaded:
                error_message = DegreeCSVIngestionErrorMessages.LOGO_IMAGE_DOWNLOAD_FAILURE.format(
                    degree_slug=degree.marketing_slug
                )
                logger.error(error_message)
                self._register_ingestion_error(DegreeCSVIngestionErrors.LOGO_IMAGE_DOWNLOAD_FAILURE, error_message)

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
            error_dict = self.MODEL_ERROR_MAPPING[model]
            error_message = error_dict['error_message'].format(
                value,
                degree_slug=degree_slug,
            )
            error_type = error_dict['error_type']

            logger.exception(error_message)
            self._register_ingestion_error(error_type, error_message)
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
