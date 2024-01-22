"""
Django management command to fetch Outcome surveys from Snowflake and add them in CourseReview model.
"""
import logging

import snowflake.connector
from django.conf import settings
from django.core.management import BaseCommand, CommandError

from course_discovery.apps.course_metadata.constants import SNOWFLAKE_REFRESH_COURSE_REVIEWS_QUERY
from course_discovery.apps.course_metadata.models import CourseReview

LOGGER = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Django management command to fetch Outcome surveys from Snowflake and add them in CourseReview model.

    Example usage:
    ./manage.py refresh_course_reviews
    ./manage.py refresh_course_reviews --dry-run
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            dest='dry_run',
            default=False,
            help='Dry Run, print log messages without committing anything in database.',
        )

    def get_query_results_from_snowflake(self):
        """
        Get query results from Snowflake and yield each row.
        """

        ctx = snowflake.connector.connect(
            user=settings.SNOWFLAKE_SERVICE_USER,
            password=settings.SNOWFLAKE_SERVICE_USER_PASSWORD,
            account=settings.SNOWFLAKE_ACCOUNT,
            database=settings.SNOWFLAKE_DATABASE
        )
        cs = ctx.cursor()
        try:
            cs.execute(SNOWFLAKE_REFRESH_COURSE_REVIEWS_QUERY)
            rows = cs.fetchall()
            for row in rows:
                yield row
        finally:
            cs.close()
        ctx.close()

    def handle(self, *args, **options):
        should_commit = not options['dry_run']

        course_review_failure_keys = []
        course_review_record_created = 0
        LOGGER.info(f'[Refresh Course Reviews]  Process started with option dry_run={should_commit}.')
        for next_row in self.get_query_results_from_snowflake():
            course_key = next_row[0]
            defaults = {
                'reviews_count': next_row[1],
                'avg_course_rating': next_row[2],
                'confident_learners_percentage': next_row[3],
                'most_common_goal': next_row[4],
                'most_common_goal_learners_percentage': next_row[5],
                'total_enrollments': next_row[6]
            }
            LOGGER.info(
                f'[Refresh Course Reviews] Creating/updating record with following data for {course_key}: {defaults}'
            )

            if should_commit:
                try:
                    _, created = CourseReview.objects.update_or_create(
                        course_key=course_key,
                        defaults=defaults,
                    )
                    if created:
                        course_review_record_created += 1
                except Exception as exc:  # pylint: disable=broad-except
                    LOGGER.exception(f'[Refresh Course Reviews] Failed to create or update course review record for '
                                     f'course key: {course_key} with the following error: {exc}')
                    course_review_failure_keys.append(course_key)

        LOGGER.info(
            f'''[Refresh Course Reviews] Execution completed.
            Course Reviews Created: {course_review_record_created}
            Courses Reviews create/update failed: {len(course_review_failure_keys)}
            {f'Keys of courses with failures: {course_review_failure_keys}' if course_review_failure_keys else ''}
            '''
        )

        if course_review_failure_keys:
            raise CommandError('One or more course reviews were not successfully created or updated. Please check '
                               'above logs for more details.')
