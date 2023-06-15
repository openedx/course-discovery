import logging

import unicodecsv
from django.conf import settings
from django.core.management import BaseCommand, CommandError

from course_discovery.apps.course_metadata.emails import send_email_for_slug_updates
from course_discovery.apps.course_metadata.models import Course, MigrateCourseSlugConfiguration
from course_discovery.apps.course_metadata.utils import get_slug_for_course, is_valid_slug_format, is_valid_uuid

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """
    It will update course url slugs to the new format i.e 'learn/<primary_subject>/<organization_name>-course_title'
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry_run',
            help='Just display updated slugs, do not commit in DB',
            type=bool,
        )
        parser.add_argument(
            '--course_uuids',
            action='append',
            default=[],
            help="Course_uuid list [,]",
        )
        parser.add_argument(
            '--args_from_database',
            help='Get CSV from MigrateCourseSlugConfiguration model',
            type=str,
        )
        parser.add_argument(
            '--limit',
            help='Limit of number of courses to update their slugs',
            type=int,
            default=0,
        )

    def handle(self, *args, **options):
        """
        It will execute the command to update slugs to new format
        'learn/<primary_subject>/<organization_name>-course_title'
        """
        self.slug_update_report = []  # pylint: disable=attribute-defined-outside-init
        dry_run = options.get('dry_run', False)
        course_uuids = options.get('course_uuids', None)
        csv_from_config = options.get('args_from_database', None)
        limit = options.get('limit', None)
        courses = []

        if csv_from_config:
            courses = self._get_courses_from_csv_config()

        if course_uuids:
            courses = self._get_courses_from_uuids(course_uuids)

        if limit:
            logger.info(f"Getting first {limit} open course records")
            courses = Course.everything.filter(product_source__slug='edx')[:limit]

        for course in courses:
            self._update_course_slug(course, dry_run)

        send_email_for_slug_updates(self.slug_update_report, settings.NOTIFY_SLUG_UPDATE_RECIPIENTS)
        self._log_report_in_csv_format()

    def _add_to_slug_update_report(self, course, new_slug=None, error=None):
        """
        It will add course and slug information in slug_update_report to show stats
        """
        if error:
            logger.warning(error)
        self.slug_update_report.append(
            {
                'course_uuid': course.uuid,
                'old_slug': course.active_url_slug,
                'new_slug': new_slug,
                'error': error
            }
        )

    def _update_course_slug(self, course, dry_run=False):
        """
        It will update course slug to new format if its not already in new format and commit in DB only if dry run is
        False
        """
        try:
            current_slug = course.active_url_slug
            if current_slug and is_valid_slug_format(current_slug):
                error_msg = f"Course with uuid {course.uuid} and title {course.title} slug is already in correct " \
                            f"format '{current_slug}'"
                logger.info(error_msg)
                self._add_to_slug_update_report(course, error=error_msg)
            else:
                logger.info(f"Updating slug for course with uuid {course.uuid} and title {course.title}, "
                            f"current slug is '{current_slug}'")
                new_slug, error = get_slug_for_course(course)
                self._add_to_slug_update_report(course, new_slug, error)
                if not dry_run and new_slug:
                    course.set_active_url_slug(new_slug)
                    if course.official_version:
                        logger.info(f"Updating slug for non-draft course with uuid {course.official_version.uuid} and "
                                    f"title {course.official_version.title} from "
                                    f"'{course.official_version.current_slug}' to '{new_slug}'")
                        course.official_version.set_active_url_slug(new_slug)
                    logger.info(f"Updated slug for course with uuid {course.uuid} and title {course.title} "
                                f"from '{current_slug}' to '{new_slug}'")
        except Exception as ex:  # pylint: disable=broad-except
            logger.error(f"Error occurred during update course slug process, error: {ex}")
            self._add_to_slug_update_report(course, error=str(ex))

    def _get_courses_from_csv_config(self):
        csv_loader_config = MigrateCourseSlugConfiguration.current()
        csv_file = csv_loader_config.csv_file if csv_loader_config.is_enabled() else None
        if not csv_file:
            raise CommandError("No CSV file is given to MigrateCourseSlugConfiguration model")
        rows = list(unicodecsv.DictReader(csv_file))
        course_uuids = [row['course_uuids'] for row in rows]
        return self._get_courses_from_uuids(course_uuids)

    @staticmethod
    def _get_courses_from_uuids(course_uuids):
        valid_course_uuids = []
        for course_uuid in course_uuids:
            if is_valid_uuid(course_uuid):
                valid_course_uuids.append(course_uuid)
            else:
                logger.info(f"Skipping uuid {course_uuid} because of incorrect format")

        return Course.everything.filter(product_source__slug='edx', uuid__in=valid_course_uuids)

    def _log_report_in_csv_format(self):
        report_in_csv_format = "course_uuid,old_slug,new_slug,error\n"

        for record in self.slug_update_report:
            report_in_csv_format = report_in_csv_format + f"{record['course_uuid']},{record['old_slug']}," \
                                                          f"{record['new_slug']},{record['error']}\n"

        logger.info(report_in_csv_format)
