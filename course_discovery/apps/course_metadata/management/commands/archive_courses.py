"""
Management command for archiving courses in bulk

Example usage:
    $ ./manage.py archive_courses --from-db

Use ./manage.py archive_courses --help for more information on the available arguments and their behavior
"""
import csv
import io
import logging
from datetime import timedelta
from functools import reduce

import unicodecsv
from django.db import transaction
from django.conf import settings
from django.core.management import BaseCommand, CommandError
from django.utils import timezone

from course_discovery.apps.api.utils import StudioAPI
from course_discovery.apps.course_metadata.choices import ExternalProductStatus
from course_discovery.apps.course_metadata.emails import send_email_for_course_archival
from course_discovery.apps.course_metadata.models import ArchiveCoursesConfig, Course, CourseRunStatus, CourseType

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Archive a collection of courses"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.report = {
            'failures': [],
            'successes': [],
            'total_count': 0
        }

    def add_arguments(self, parser):
        parser.add_argument(
            '--from-db',
            help='Query the db for the uuids to archive. The uuids are fetched from the ArchiveCoursesConfig model',
            default=False,
            action='store_true'
        )
        parser.add_argument(
            '--type',
            type=str,
            help="The course type to archive",
            default="",
            metavar="COURSE_TYPE"
        )
        parser.add_argument(
            '--mangle-end-date',
            help="Set the end date and enrollment end date for the archived courses' runs in the past",
            default=False,
            action='store_true'
        )
        parser.add_argument(
            '--mangle-title',
            help="Prepend 'DELETED' to the titles of the archived courses",
            default=False,
            action='store_true'
        )

    def handle(self, *args, **options):
        from_db = options.get('from_db')
        course_type = options.get('type')
        mangle_end_date = options.get('mangle_end_date')
        mangle_title = options.get('mangle_title')

        if from_db:
            courses = Course.objects.filter(uuid__in=self.get_uuids_from_database())
        elif course_type:
            courses = Course.objects.filter(
                type__in=[CourseType.objects.get(slug__in=[course_type, course_type.lower()])]
            )
        else:
            raise CommandError("Please provide one of --type or --from-db")

        self.report['total_count'] = courses.count()

        for course in courses:
            # Store the original title in case we mangle it
            course_title = course.title
            try:
                self.archive(course, mangle_end_date, mangle_title)
                if course.draft_version:
                    self.archive(course.draft_version, mangle_end_date, mangle_title)
            except Exception as exc: # pylint: disable=broad-exception-caught
                self.report['failures'].append(
                    {
                        'uuid': course.uuid,
                        'title': course_title,
                        'reason': repr(exc)
                    }
                )
                logger.exception(f'Failed to archive course with uuid {course.uuid}')
            else:
                self.report['successes'].append(
                    {
                        'uuid': course.uuid,
                        'title': course_title
                    }
                )
                logger.info(f"Successfully archived course with uuid: {course.uuid}")

        send_email_for_course_archival(self.report, self.get_csv_report(), settings.COURSE_ARCHIVAL_MAIL_RECIPIENTS)

    @transaction.atomic
    def archive(self, course, mangle_end_date, mangle_title):
        for course_run in course.course_runs.all():
            course_run.status = CourseRunStatus.Unpublished
            course_run.save(update_fields=['status'])

            if mangle_end_date and course_run.end and course_run.end > timezone.now():
                course_run.end = timezone.now()
            if mangle_end_date and course_run.enrollment_end and course_run.enrollment_end > timezone.now():
                course_run.enrollment_end = timezone.now() - timedelta(days=1)
            course_run.save(update_fields=['end', 'enrollment_end'])

            # Push to studio to prevent RCM rewrite
            if mangle_end_date and not course_run.draft:
                api = StudioAPI(course_run.course.partner)
                api._update_end_date_in_studio(course_run) # pylint: disable=protected-access

        if course.additional_metadata:
            course.additional_metadata.product_status = ExternalProductStatus.Archived
            if course.additional_metadata.end_date and course.additional_metadata.end_date > timezone.now():
                course.additional_metadata.end_date = timezone.now()
            course.additional_metadata.save(update_fields=['product_status', 'end_date'])

        if mangle_title and not course.title.startswith('DELETED'):
            course.title = f"DELETED - {course.title}"
            course.save(update_fields=['title'])

    def get_uuids_from_database(self):
        config = ArchiveCoursesConfig.current()
        if not config.enabled:
            raise CommandError('Configuration object is not enabled')

        if not config.csv_file:
            raise CommandError('Configuration object does not have any input csv')

        reader = unicodecsv.DictReader(config.csv_file)
        uuid_list = reduce(lambda uuid_list, row: uuid_list + list(row.values()), reader, [])
        return uuid_list

    def get_csv_report(self):
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['course_uuid', 'title', 'status'])
        for record in self.report['successes']:
            writer.writerow([record['uuid'], record['title'], 'success'])
        for record in self.report['failures']:
            writer.writerow([record['uuid'], record['title'], 'failure'])

        return output.getvalue()
