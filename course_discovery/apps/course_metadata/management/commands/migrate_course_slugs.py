import logging
import unicodecsv
from django.core.management import BaseCommand, CommandError

from course_discovery.apps.course_metadata.models import Course, MigrateCourseSlugConfiguration
from course_discovery.apps.course_metadata.emails import send_email_for_slug_updates
from course_discovery.apps.course_metadata.utils import get_slug_for_course, is_valid_uuid, is_valid_slug_format

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = ''

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
            default=1,
        )

    def handle(self, *args, **options):
        """
        to add
        """
        self.slug_update_report = []
        dry_run = options.get('dry_run', False)
        course_uuids = options.get('course_uuids', None)
        csv_from_config = options.get('args_from_database', None)
        limit = options.get('limit', None)
        courses = []

        if csv_from_config:
            courses = self.get_courses_from_csv_config()

        if course_uuids:
            courses = self.get_courses_from_uuids(course_uuids)

        if limit:
            logger.info(f"Getting first {limit} open course records")
            courses = Course.everything.filter(product_source__slug='edx')[:limit]

        for course in courses:
            self.update_course_slug(course, dry_run)

        send_email_for_slug_updates(self.slug_update_report)
        self.log_report_in_csv_format()

    def add_to_slug_update_report(self, course, new_slug=None, error=None):
        """
        It will add course and slug information in slug_update_report to show stats
        """
        self.slug_update_report.append(
            {
                'course_uuid': course.uuid,
                'old_slug': course.active_url_slug,
                'new_slug': new_slug,
                'error': error
            }
        )

    def update_course_slug(self, course, dry_run=False):
        """
        It will update course slug to new format if its not already in new format and commit in DB only if dry run is
        False
        """
        current_slug = course.active_url_slug
        if is_valid_slug_format(current_slug):
            error_msg = f"Course with uuid {course.uuid} and title {course.title} slug is already in correct " \
                        f"format '{current_slug}'"
            logger.info(error_msg)
            self.add_to_slug_update_report(course, error=error_msg)
        else:
            logger.info(f"Updating slug for course with uuid {course.uuid} and title {course.title}, "
                        f"current slug is '{current_slug}'")
            new_slug, error = get_slug_for_course(course)
            self.add_to_slug_update_report(course, new_slug, error)
            if not dry_run:
                course.set_active_url_slug(new_slug)
                logger.info(f"Updated slug for course with uuid {course.uuid} and title {course.title} "
                            f"from '{current_slug}' to '{new_slug}'")

    def get_courses_from_csv_config(self):
        csv_loader_config = MigrateCourseSlugConfiguration.current()
        csv_file = csv_loader_config.csv_file if csv_loader_config.is_enabled() else None
        rows = list(unicodecsv.DictReader(csv_file))
        course_uuids = [row['course_uuids'] for row in rows]
        return self.get_courses_from_uuids(course_uuids)

    @staticmethod
    def get_courses_from_uuids(course_uuids):
        valid_course_uuids = []
        for course_uuid in course_uuids:
            if is_valid_uuid(course_uuid):
                valid_course_uuids.append(course_uuid)
            else:
                logger.info(f"Skipping uuid {course_uuid} because of incorrect format")

        return Course.everything.filter(product_source__slug='edx', uuid__in=valid_course_uuids)

    def log_report_in_csv_format(self):
        report_in_csv_format = "course_uuid,old_slug,new_slug,error\n"

        for record in self.slug_update_report:
            report_in_csv_format = report_in_csv_format + f"{record['course_uuid']},{record['old_slug']}," \
                                                          f"{record['new_slug']},{record['error']}\n"

        logger.info(report_in_csv_format)
