"""
Data loader responsible for creating degree entries in discovery Database,
"""
import csv
import logging

from course_discovery.apps.course_metadata.choices import ProgramStatus
from course_discovery.apps.course_metadata.data_loaders import AbstractDataLoader
from course_discovery.apps.course_metadata.models import (
    Degree, DegreeAdditionalMetadata, Organization, Program, ProgramType
)
from course_discovery.apps.course_metadata.utils import download_and_save_program_image

logger = logging.getLogger(__name__)


class DegreeCSVDataLoader(AbstractDataLoader):

    def __init__(self, partner, api_url=None, max_workers=None, is_threadsafe=False, csv_path=None):
        super().__init__(partner, api_url, max_workers, is_threadsafe)

        self.messages_list = []  # to show failure/skipped ingestion message at the end
        self.degree_uuids = {}  # to show the discovery degrees/program ids for each processed degree
        try:
            self.reader = csv.DictReader(open(csv_path, 'r'))   # lint-amnesty, pylint: disable=consider-using-with
        except FileNotFoundError:
            logger.exception("Error opening csv file at path {}".format(csv_path))    # lint-amnesty, pylint: disable=logging-format-interpolation
            raise  # re-raising exception to avoid moving the code flow

    def ingest(self):  # pylint: disable=too-many-statements
        logger.info("Initiating Degree CSV data loader flow.")
        for row in self.reader:
            # TODO: test and decide if need to make transaction atomic
            # with transaction.atomic():

            row = self.transform_dict_keys(row)
            degree_title = row['title']
            external_identifier = row['identifier']
            org_key = row['organization_key']

            logger.info('Starting data import flow for {}'.format(degree_title))    # lint-amnesty, pylint: disable=logging-format-interpolation

            if not Organization.objects.filter(key=org_key).exists():
                logger.error("Organization {} does not exist. Skipping CSV loader for degree {}".format(   # lint-amnesty, pylint: disable=logging-format-interpolation
                    org_key,
                    degree_title
                ))
                self.messages_list.append('[MISSING ORGANIZATION] org: {}, degree: {}'.format(
                    org_key, degree_title
                ))
                continue

            try:
                program_type = ProgramType.objects.get(slug=row['product_type'])
            except ProgramType.DoesNotExist:
                logger.exception("ProgramType {} does not exist in the database.".format(    # lint-amnesty, pylint: disable=logging-format-interpolation
                    row['product_type']
                ))
                continue

            message = self.validate_degree_data(program_type, row)
            if message:
                logger.error("Data validation issue for degree {}, skipping ingestion".format(degree_title))    # lint-amnesty, pylint: disable=logging-format-interpolation
                self.messages_list.append("[DATA VALIDATION ERROR] Degree {}. Missing data: {}".format(
                    degree_title, message
                ))
                continue

            # TODO: handle org override
            # simple field populate

            # get degree object from title
            degree = Degree.objects.filter(title=degree_title, partner=self.partner).first()

            degree_title = degree.title if degree else degree_title

            if degree:
                logger.info("Degree {} is located in the database.".format(degree_title))    # lint-amnesty, pylint: disable=logging-format-interpolation

                additional_metadata = DegreeAdditionalMetadata.objects.filter(degree=degree).first()

                if not additional_metadata or \
                        additional_metadata.external_identifier == external_identifier:
                    try:
                        self._update_degree(row, degree, program_type)
                    except Exception:  # pylint: disable=broad-except
                        logger.exception("An unknown error occurred while updating degree information")
                        self.messages_list.append('[DEGREE UPDATE ERROR] degree {}'.format(degree_title))
                        continue
                else:
                    logger.error("Skipping Degree {} Othrwise it will overwrite existing OCM degree data.".format(    # lint-amnesty, pylint: disable=logging-format-interpolation
                        degree_title
                    ))
                    self.messages_list.append('[DEGREE UPDATE ERROR] degree {}'.format(degree_title))
                    continue
            else:
                logger.info("Degree Program {} could not be found in database, creating the degree.".format(    # lint-amnesty, pylint: disable=logging-format-interpolation
                    degree_title
                ))
                try:
                    degree = self._create_degree(row, program_type)
                except Exception:  # pylint: disable=broad-except
                    logger.exception("Error occurred when attempting to create a new degree against key {}".format(    # lint-amnesty, pylint: disable=logging-format-interpolation
                        degree_title
                    ))
                    self.messages_list.append('[DEGREE CREATION ERROR] degree {}'.format(degree_title))
                    continue
                degree = Degree.objects.get(uuid=degree.uuid, partner=self.partner)

            program = Program.objects.get(degree=degree, partner=self.partner)
            is_downloaded = download_and_save_program_image(program, row['card_image_url'])
            if not is_downloaded:
                logger.error("Unexpected error happened while downloading image for degree {}".format(  # lint-amnesty, pylint: disable=logging-format-interpolation
                    degree_title
                ))
                self.messages_list.append('[IMAGE DOWNLOAD FAILURE] degree {}'.format(degree_title))
                continue

            logger.info("Degree updated successfully for degree key {}".format(degree.uuid))    # lint-amnesty, pylint: disable=logging-format-interpolation
            self.degree_uuids[str(degree.uuid)] = degree_title

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

    def _create_degree(self, data, program_type):
        """
        Make a degree object through ORM
        """
        org = Organization.objects.get(key=data['organization_key'])

        degree = Degree.objects.create(
            title=data['title'],
            type=program_type,
            status=ProgramStatus.Unpublished,
            marketing_slug=data['slug'],
            overview=data['overview'],
            partner=self.partner,
        )
        if degree:
            logger.info("Degree with title {} has been created".format(    # lint-amnesty, pylint: disable=logging-format-interpolation
                degree,
            ))

            degree.authoring_organizations.add(org)
            additional_metadata = DegreeAdditionalMetadata.objects.create(
                external_identifier=data['identifier'],
                organic_url=data['organic_url'],
                external_url=data['paid_landing_page_url'],
                degree=degree
            )

            if additional_metadata:
                logger.info("AdditionalMetdata {} has been created with Degree title {}".format(    # lint-amnesty, pylint: disable=logging-format-interpolation
                    additional_metadata,
                    degree,
                ))

        return degree

    def _update_degree(self, data, degree, program_type):
        """
        Update degree object through ORM
        """
        updated = Degree.objects.filter(title=degree.title).update(
            type=program_type,
            status=ProgramStatus.Unpublished,
            marketing_slug=data['slug'],
            overview=data['overview'],
            partner=self.partner,
        )
        if updated:
            logger.info("Degree with title {} is updated".format(    # lint-amnesty, pylint: disable=logging-format-interpolation
                degree,
            ))
        else:
            logger.error("Degree with title {} has not been updated".format(    # lint-amnesty, pylint: disable=logging-format-interpolation
                degree,
            ))
            return

        org = Organization.objects.get(key=data['organization_key'])
        degree.authoring_organizations.clear()
        degree.authoring_organizations.add(org)

        additional_metadata_dict = {
            "external_identifier": data['identifier'],
            "organic_url": data['organic_url'],
            "external_url": data['paid_landing_page_url'],
        }

        additional_metadata, created = DegreeAdditionalMetadata.objects.update_or_create(
            degree=degree,
            defaults=additional_metadata_dict
        )

        if created:
            logger.info("AdditionalMetdata {} has been created with Degree title {}".format(    # lint-amnesty, pylint: disable=logging-format-interpolation
                additional_metadata,
                degree,
            ))
