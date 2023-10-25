import logging
from csv import DictReader

from django.conf import settings
from django.core.management import BaseCommand, CommandError

from course_discovery.apps.course_metadata.emails import send_email_for_slug_updates
from course_discovery.apps.course_metadata.models import Course, MigrateCourseSlugConfiguration
from course_discovery.apps.course_metadata.utils import is_valid_slug_format, is_valid_uuid

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "It will update the course url slugs of existing courses to slugs present in the csv file"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.slug_update_report = []

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv_file",
            type=str,
            help="csv file with course uuids and url slugs",
            required=False,
        )
        parser.add_argument(
            "--args_from_db",
            type=bool,
            help='Use arguments from the MigrateCourseSlugConfiguration model instead of the command line.',
            default=True,
        )

    def handle(self, *args, **options):
        """
        Command to update he course url slugs of existing courses to slugs present in the csv file
        """
        csv_file_path = options.get('csv_file', None)
        args_from_database = options.get('args_from_db')
        if args_from_database:
            csv_from_config = MigrateCourseSlugConfiguration.current()

        try:
            if csv_file_path:
                file_reader = DictReader(open(csv_file_path, 'r'))  # pylint: disable=consider-using-with
                logger.info(f'Reading csv file from path: {csv_file_path}')
            else:
                file = csv_from_config.csv_file if csv_from_config.is_enabled() else None
                file_reader = DictReader(file.open('r'))
                logger.info(f'Reading csv file from config MigrateCourseSlugConfiguration {csv_from_config.csv_file}')

        except Exception as exc:
            raise CommandError(  # pylint: disable=raise-missing-from
                'Error occured while opening the url slugs csv.\n{}'.format(exc)
            )

        for row in file_reader:
            course_uuid, course_url_slug = row.get('course_uuid', None), row.get('course_url_slug', None)
            if not is_valid_uuid(course_uuid):
                error_msg = f'Invalid course uuid: {course_uuid}'
                logger.error(error_msg)
                self._add_records_to_update_slugs_summary_report(course_uuid=course_uuid, error_msg=error_msg)
                continue
            if not course_url_slug or not is_valid_slug_format(course_url_slug):
                error_msg = f'Invalid course url slug: {course_url_slug}'
                logger.error(error_msg)
                self._add_records_to_update_slugs_summary_report(course_uuid, error_msg=error_msg)
                continue
            try:
                self.update_course_slug(course_uuid, course_url_slug)
            except Exception as exc:  # pylint: disable=broad-except
                logger.error(f'Error occured while updating the course url slug.\n{exc}')

        send_email_for_slug_updates(
            stats=self._get_report_in_csv_format(),
            to_users=settings.NOTIFY_SLUG_UPDATE_RECIPIENTS,
            subject='Course URL Slugs Update Report'
        )

        self._log_report_in_csv_format()

    def _get_report_in_csv_format(self):
        """
        Get the course url slug update report in csv format
        """
        report_in_csv_format = "course_uuid,old_url_slug,new_url_slug,error_msg\n"

        for record in self.slug_update_report:
            report_in_csv_format += f"{record['course_uuid']},{record['old_url_slug']}," \
                f"{record['new_url_slug']},{record['error_msg']}\n"
        return report_in_csv_format

    def _log_report_in_csv_format(self):
        """
        Log the course url slug update report in csv format
        """
        report_in_csv_format = self._get_report_in_csv_format()
        logger.info(f'Course url slug update report in csv format:\n {report_in_csv_format}')

    def _add_records_to_update_slugs_summary_report(
        self, course_uuid=None, old_url_slug=None, new_url_slug=None, error_msg=None
    ):
        """
        Add the course url slug update record to the summary report
        """
        self.slug_update_report.append({
            'course_uuid': course_uuid,
            'old_url_slug': old_url_slug,
            'new_url_slug': new_url_slug,
            'error_msg': error_msg
        })

    def update_course_slug(self, course_uuid, course_url_slug):
        """
        Update the course url slug of a course with the given course_uuid
        """
        error_msg = None
        old_url_slug = None
        course = None
        try:
            course = Course.everything.get(uuid=course_uuid, draft=True)
            old_url_slug = course.active_url_slug
            course.set_active_url_slug(course_url_slug)
            if course.official_version:
                course.official_version.set_active_url_slug(course_url_slug)
            logger.info(f'Updated the course url slug of course:{course_uuid} from {old_url_slug} to {course_url_slug}')
        except Course.DoesNotExist:
            error_msg = f'Course with uuid: {course_uuid} does not exist'
            logger.error(error_msg)
        except Exception as exc:  # pylint: disable=broad-except
            error_msg = f'Error occured while updating the course url slug.\n{exc}'
            logger.error(error_msg)
        finally:
            active_url_slug = course.active_url_slug if course else None
            self._add_records_to_update_slugs_summary_report(course_uuid, old_url_slug, active_url_slug, error_msg)
