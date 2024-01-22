import logging

import unicodecsv
from django.conf import settings
from django.core.management import BaseCommand, CommandError

from course_discovery.apps.course_metadata.emails import send_email_for_slug_updates
from course_discovery.apps.course_metadata.models import Course, CourseType, MigrateCourseSlugConfiguration
from course_discovery.apps.course_metadata.utils import get_slug_for_course, is_valid_slug_format, is_valid_uuid

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """
    It will update course url slugs to the format 'learn/<primary_subject>/<organization_name>-<course_title>' for
    open courses, 'executive-education/<organization_name>-<course_title>' for executive education courses, and
    'boot-camps/<primary-subject>/<organization_name>-<course_title>' for bootcamps
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.slug_update_report = []
        self.course_type = None
        self.product_source = None

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
            '--csv_from_config',
            help='Get CSV from MigrateCourseSlugConfiguration model',
            type=str,
        )
        parser.add_argument(
            '--limit',
            help='Limit of number of courses to update their slugs',
            type=int,
            default=0,
        )
        parser.add_argument(
            '--args_from_database',
            action='store_true',
            help='Use arguments from the MigrateCourseSlugConfiguration model instead of the command line.',
        )
        parser.add_argument(
            '--course_type',
            help='Course Type to update slug',
            type=str,
            choices=[CourseType.BOOTCAMP_2U, CourseType.EXECUTIVE_EDUCATION_2U, 'open-course'],
            default='open-course',
        )
        parser.add_argument(
            '--product_source',
            help='Product source slug of the courses',
            type=str,
            default='edx',
        )

    def get_args_from_database(self):
        config = MigrateCourseSlugConfiguration.current()
        if not config.is_enabled():
            raise CommandError('Configuration object is not enabled')

        if not (config.course_uuids or bool(config.csv_file) or config.count):
            raise CommandError('Configuration object does not have any input type')

        return {
            'dry_run': config.dry_run,
            'course_uuids': config.course_uuids.split() if config.course_uuids else None,
            'csv_from_config': config.csv_file if bool(config.csv_file) else None,
            'limit': config.count,
            'course_type': config.course_type,
            'product_source': config.product_source.slug,
        }

    def handle(self, *args, **options):
        """
        It will execute the command to update slugs to the sub directory format i.e
        'learn/<primary_subject>/<organization_name>-<course_title>' for open courses
        'executive-education/<organization_name>-<course_title>' for executive education courses
        """
        args_from_database = options.get('args_from_database', None)
        if args_from_database:
            options = self.get_args_from_database()
        dry_run = options.get('dry_run', False)
        course_uuids = options.get('course_uuids', None)
        csv_from_config = options.get('csv_from_config', None)
        limit = options.get('limit', None)
        self.course_type = options.get('course_type', 'open-course')
        self.product_source = options.get('product_source', 'edx')
        courses = []

        if csv_from_config:
            courses = self._get_courses_from_csv_file(csv_from_config)

        if course_uuids:
            courses = self._get_courses_from_uuids(course_uuids)

        if limit:
            logger.info(f"Getting first {limit} {self.course_type} records")
            courses = self._get_courses()[:limit]

        for course in courses:
            self._update_course_slug(course, dry_run)

        send_email_for_slug_updates(self._get_report_in_csv_format(), settings.NOTIFY_SLUG_UPDATE_RECIPIENTS)
        self._log_report_in_csv_format()

    def _add_to_slug_update_report(self, course, new_slug=None, error=None):
        """
        It will add course and slug information in slug_update_report to show stats
        """
        if error:
            logger.info(error)
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
        Given a course and it will update its slug to sub-directory format if its not already and commit in DB only if
        dry run is False
        """
        try:
            current_slug = course.active_url_slug
            if current_slug and is_valid_slug_format(current_slug):
                error_msg = f"Course with uuid {course.uuid} and title {course.title} has slug already in correct " \
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
                        logger.info(f"Updating slug for non-draft course with title {course.official_version.title} "
                                    f"from '{course.official_version.active_url_slug}' to '{new_slug}'")
                        course.official_version.set_active_url_slug(new_slug)
                    logger.info(f"Updated slug for course with uuid {course.uuid} and title {course.title} "
                                f"from '{current_slug}' to '{new_slug}'")
        except Exception as ex:  # pylint: disable=broad-except
            logger.error(f"Error occurred during update course slug process, error: {ex}")
            self._add_to_slug_update_report(course, error=str(ex))

    def _get_courses_from_csv_file(self, csv_file):
        rows = list(unicodecsv.DictReader(csv_file))
        course_uuids = [row['course_uuids'] for row in rows]
        return self._get_courses_from_uuids(course_uuids)

    def _get_courses_from_uuids(self, course_uuids):
        valid_course_uuids = []
        for course_uuid in course_uuids:
            if is_valid_uuid(course_uuid):
                valid_course_uuids.append(course_uuid)
            else:
                error = f"Skipping uuid {course_uuid} because of incorrect format"
                self.slug_update_report.append(
                    {
                        'course_uuid': course_uuid,
                        'old_slug': None,
                        'new_slug': None,
                        'error': error
                    }
                )
                logger.info(error)
        return self._get_courses().filter(uuid__in=valid_course_uuids)

    def _get_courses(self):
        courses = Course.everything.filter(product_source__slug=self.product_source, draft=True)
        if self.course_type == CourseType.EXECUTIVE_EDUCATION_2U:
            return courses.filter(type__slug=CourseType.EXECUTIVE_EDUCATION_2U)
        elif self.course_type == CourseType.BOOTCAMP_2U:
            return courses.filter(type__slug=CourseType.BOOTCAMP_2U)
        # Return Open Courses only
        return courses.exclude(type__slug__in=[CourseType.EXECUTIVE_EDUCATION_2U, CourseType.BOOTCAMP_2U])

    def _get_report_in_csv_format(self):
        report_in_csv_format = "course_uuid,old_slug,new_slug,error\n"

        for record in self.slug_update_report:
            report_in_csv_format = report_in_csv_format + f"{record['course_uuid']},{record['old_slug']}," \
                                                          f"{record['new_slug']},{record['error']}\n"

        return report_in_csv_format

    def _log_report_in_csv_format(self):
        report_in_csv_format = self._get_report_in_csv_format()
        logger.info(report_in_csv_format)
