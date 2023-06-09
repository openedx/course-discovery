
import unicodecsv

from django.core.management import BaseCommand, CommandError
from course_discovery.apps.course_metadata.models import Course, MigrateCourseSlugConfiguration
from course_discovery.apps.course_metadata.utils import get_slug_for_course, validate_slug_format


class Command(BaseCommand):
    help = ''

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry_run',
            help='dry run',
            type=bool,
        )
        parser.add_argument(
            '--course_uuids',
            action='append',
            default=[],
            help="course_uuid list [,]"
        )
        parser.add_argument(
            '--args_from_database',
            help='Get CSV from MigrateCourseSlugConfiguration model',
            type=str,
        )

    def handle(self, *args, **options):
        """
        to add
        """
        self.slug_update_report = []
        dry_run = options.get('dry_run', False)
        course_uuids = options.get('course_uuids', None)
        csv_from_config = options.get('args_from_database', None)

        if csv_from_config:
            csv_loader_config = MigrateCourseSlugConfiguration.current()
            csv_file = csv_loader_config.csv_file if csv_loader_config.is_enabled() else None
            rows = list(unicodecsv.DictReader(csv_file))
            course_uuids = [row['course_uuids'] for row in rows]
            courses = Course.objects.filter(uuid__in=course_uuids)
        if course_uuids:
            # TODO: skip invalid uuid
            courses = Course.objects.filter(uuid__in=course_uuids)

        for course in courses:
            if dry_run:
                new_slug = get_slug_for_course(course)
                self.log_slug_change(course, new_slug)
            else:
                self.update_course_slug(course)

        print(self.slug_update_report)

    def log_slug_change(self, course, new_slug=None, error=None):
        self.slug_update_report.append(
            {
                'course_uuid': course.uuid,
                'old_slug': course.active_url_slug,
                'new_slug': new_slug,
                'error': error
            }
        )

    def update_course_slug(self, course):
        current_slug = course.active_url_slug
        if validate_slug_format(current_slug):
            self.log_slug_change(course, error='slug is already in correct format')
        else:
            new_slug = get_slug_for_course(course)
            self.log_slug_change(course, new_slug)
            course.set_active_url_slug(new_slug)

