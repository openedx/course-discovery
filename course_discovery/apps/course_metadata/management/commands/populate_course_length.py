"""
Django management command to populate course_length in Course model by fetching data from snowflake.
"""
import logging

import snowflake.connector
from django.conf import settings
from django.core.management import BaseCommand

from course_discovery.apps.course_metadata.constants import SNOWFLAKE_POPULATE_COURSE_LENGTH_QUERY
from course_discovery.apps.course_metadata.models import Course

LOGGER = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Django management command to populate course length field in Course model by fetching data from snowflake.

    Example usage:
    ./manage.py populate_course_length
    ./manage.py populate_course_length --no-commit
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--no-commit',
            action='store_true',
            dest='no_commit',
            default=False,
            help='Dry Run, print log messages without committing anything.',
        )

    def get_query_results_from_snowflake(self):
        """
        Get query results from Snowflake and yield each row.
        """
        ctx = snowflake.connector.connect(
            user=settings.SNOWFLAKE_SERVICE_USER,
            password=settings.SNOWFLAKE_SERVICE_USER_PASSWORD,
            account='edx.us-east-1',
            database='prod'
        )
        cs = ctx.cursor()
        try:
            cs.execute(SNOWFLAKE_POPULATE_COURSE_LENGTH_QUERY)
            rows = cs.fetchall()
            for row in rows:
                yield row
        finally:
            cs.close()
        ctx.close()

    def handle(self, *args, **options):
        should_commit = not options['no_commit']

        update_failure_uuids = []
        courses_updated = 0
        LOGGER.info(f'[Populate Course Length]  Process started with option no_commit={should_commit}.')
        for next_row in self.get_query_results_from_snowflake():
            course_uuid = next_row[0]
            course_length = next_row[2]
            LOGGER.info(
                f'[Populate Course Length] adding \'{course_length}\' as length to course with UUID {course_uuid}'
            )

            courses = Course.everything.filter(uuid=course_uuid)
            if courses:
                if should_commit:
                    courses.update(course_length=course_length)
                # if the course have draft and non draft version, updated count will still be incremented by 1 after
                # updating both versions because they both are the version of same course.
                courses_updated += 1
            else:
                update_failure_uuids.append(course_uuid)
                LOGGER.info(f'[Populate Course Length] No course found with UUID {course_uuid}')

        LOGGER.info(
            f'''[Populate Course Length] Execution completed.
            Courses Updated: {courses_updated}
            Courses Update Failed: {len(update_failure_uuids)}
            {f'UUIDs of courses with failures: {update_failure_uuids}' if update_failure_uuids else ''}
            '''
        )
