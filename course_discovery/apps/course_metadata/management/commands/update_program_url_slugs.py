import logging
import re
from csv import DictReader

from django.conf import settings
from django.core.management import BaseCommand, CommandError

from course_discovery.apps.course_metadata.constants import (
    PROGRAM_SLUG_FORMAT_REGEX, SUBDIRECTORY_PROGRAM_SLUG_FORMAT_REGEX
)
from course_discovery.apps.course_metadata.emails import send_email_for_slug_updates
from course_discovery.apps.course_metadata.models import MigrateProgramSlugConfiguration, Program
from course_discovery.apps.course_metadata.toggles import IS_SUBDIRECTORY_SLUG_FORMAT_ENABLED
from course_discovery.apps.course_metadata.utils import is_valid_uuid, transform_dict_keys

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """
    It will update program url slugs to the format 'category/subcategory/org-title' or 'category/custom-slug' for
    all degrees and programs.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.slug_update_report = []

    def add_arguments(self, parser):
        parser.add_argument(
            '--csv_file',
            help='Get CSV from MigrateProgramSlugConfiguration model',
            type=str,
        )
        parser.add_argument(
            '--args_from_database',
            action='store_true',
            help='Use arguments from the MigrateProgramSlugConfiguration model instead of the command line.',
        )

    def handle(self, *args, **options):
        """
        It will execute the command to update slugs to the sub directory format i.e
        'category/subcategory/org-title' or 'category/custom-slug' for degrees and programs
        """
        args_from_database = options.get('args_from_database', None)
        csv_file_path = options.get('csv_file', None)

        csv_from_config = MigrateProgramSlugConfiguration.current() if args_from_database else None

        try:
            if csv_file_path:
                reader = DictReader(open(csv_file_path, 'r'))  # pylint: disable=consider-using-with
            else:
                file = csv_from_config.csv_file if csv_from_config.is_enabled() else None
                reader = DictReader(file.open('r'))

        except Exception:
            raise CommandError(  # pylint: disable=raise-missing-from
                'Error reading the input data source'
            )

        logger.info('Initiating Program URL slug updation flow.')

        for row in reader:
            row = transform_dict_keys(row)
            program_uuid = row.get('uuid', None)
            new_url_slug = row.get('new_url_slug', None)

            if not self.validate_program_fields(program_uuid, new_url_slug):
                continue

            try:
                program = Program.objects.get(uuid=program_uuid)
                old_slug = program.marketing_slug
                program.marketing_slug = new_url_slug
                program.save()
                self.update_slug_report(program_uuid, None, old_slug, program.marketing_slug)
                logger.info(f'Updated Program ({program_uuid}) with slug: {old_slug} '
                            f'to new url slug: {program.marketing_slug}')

            except Program.DoesNotExist:
                error = f'Unable to locate Program instance with code {program_uuid}'
                self.update_slug_report(program_uuid, error)

            except Exception as ex:  # pylint: disable=broad-except
                error = str(ex)
                self.update_slug_report(program_uuid, error)

        csv_report = self._get_report_in_csv_format()
        send_email_for_slug_updates(
            csv_report, settings.NOTIFY_SLUG_UPDATE_RECIPIENTS, 'Migrate Program Slugs Summary Report'
        )
        logger.info(csv_report)

    def _get_report_in_csv_format(self):
        report_in_csv_format = "program_uuid,old_slug,new_slug,error\n"

        for record in self.slug_update_report:
            report_in_csv_format = f"{report_in_csv_format}{record['program_uuid']},{record['old_slug']}," \
                                   f"{record['new_slug']},{record['error']}\n"

        return report_in_csv_format

    def update_slug_report(self, uuid, error, old_slug=None, new_slug=None):
        self.slug_update_report.append(
            {
                'program_uuid': uuid,
                'old_slug': old_slug,
                'new_slug': new_slug,
                'error': error
            }
        )
        logger.info(error)

    def validate_program_fields(self, program_uuid, new_url_slug):
        """
        Checks whether a given program uuid and slug is in valid format, also updates slug report.

        Args:
            program_uuid: a program uuid
            new_url_slug: slug expected to be updated
        Returns:
            True if uuid and slug is in valid format
        """
        error = "Skipping uuid {} because of {}"
        slug_pattern = SUBDIRECTORY_PROGRAM_SLUG_FORMAT_REGEX if IS_SUBDIRECTORY_SLUG_FORMAT_ENABLED.is_enabled() \
            else PROGRAM_SLUG_FORMAT_REGEX

        if not bool(re.fullmatch(slug_pattern, new_url_slug)):
            self.update_slug_report(program_uuid, error.format(program_uuid, 'incorrect slug format'))
            return False

        if not is_valid_uuid(program_uuid):
            self.update_slug_report(program_uuid, error.format(program_uuid, 'incorrect uuid'))
            return False

        programs_qs = Program.objects.filter(marketing_slug=new_url_slug)
        if programs_qs.exists():
            self.update_slug_report(program_uuid, error.format(program_uuid, 'program with same slug already exists'))
            return False

        return True
