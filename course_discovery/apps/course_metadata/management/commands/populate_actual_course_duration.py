"""
Django management command to populate course_length in Course model by fetching data from snowflake.
"""
import logging

import snowflake.connector

from django.conf import settings
from django.core.management import BaseCommand

from course_discovery.apps.course_metadata.models import Course

LOGGER = logging.getLogger(__name__)
QUERY = '''
    WITH completions as (
    
    /* Get all completions, all time.
    */
    
    SELECT
        ccu.user_id,
        dc.course_key,
        ccu.courserun_key,
        DATE(ccu.passed_timestamp) as passed_date
    FROM
        business_intelligence.bi_course_completion as ccu
    LEFT JOIN
        core.dim_courseruns as dcr
    on
        ccu.courserun_key = dcr.courserun_key
    LEFT JOIN
        core.dim_courses as dc
    ON
        dcr.course_id = dc.course_id
    LEFT JOIN
        enterprise.ent_base_enterprise_enrollment as bee
    ON
        ccu.user_id = bee.lms_user_id AND ccu.courserun_key = bee.lms_courserun_key
    WHERE
        passed_timestamp IS NOT NULL
    
    ),
    
    time_to_pass as (
    
    /* Calculate the amount of time it took
       to pass the course for each completion.
    */
    
    
    SELECT
        completions.course_key,
        lt.user_id,
        SUM(lt.learning_time_seconds/60/60) as hours_of_learning
    FROM
        business_intelligence.learning_time as lt
    JOIN
        completions
    ON
        lt.user_id = completions.user_id
      AND
        lt.courserun_key = completions.courserun_key
      AND
        lt.date <= completions.passed_date
    JOIN
        discovery.course_metadata_courserun as disc
    ON
        lt.courserun_key = disc.key
    LEFT JOIN
        core.dim_courseruns as dim
    ON
        disc.key = dim.courserun_key
    WHERE
        disc.draft = False
    GROUP BY
        1,2
    ),
    
    courses as (
    
    /* Calculate the average amount
       of time it takes to pass a course.
        */
    
    SELECT
        course_key,
        round(AVG(hours_of_learning),1) as avg_pass_time,
        COUNT(*) as n_passed_learners
    FROM
        time_to_pass
    GROUP BY
        1
    )
    
    select
        course_key,
        avg_pass_time,
        case when avg_pass_time <= 6.5 then 'short'
        when avg_pass_time < 13 then 'medium'
        when avg_pass_time >= 13 then 'long'
        end as course_length_bin
    from
        courses
'''


class Command(BaseCommand):
    """
    Django management command to populate course duration field in Course model by fetching data from snowflake.

    Example usage:
    ./manage.py populate_actual_course_duration.py
    ./manage.py populate_actual_course_duration.py --no-commit
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
            cs.execute(QUERY)
            rows = cs.fetchall()
            for row in rows:
                yield row
        finally:
            cs.close()
        ctx.close()

    def handle(self, *args, **options):
        should_commit = not options['no_commit']

        LOGGER.info('[Populate Course Duration]  Process started.')
        for next_row in self.get_query_results_from_snowflake():
            course_key= next_row[0]
            course_duration = next_row[1]
            LOGGER.info(f'[Populate Course Duration] adding \'{course_duration}\' as duration to course with key {course_key}')
            course = Course.objects.filter(course_key=course_key)
            if should_commit:
                if course:
                    course.course_length = course_duration
                    course.save()
                else:
                    LOGGER.info(f'[Populate Course Duration] No course found with key {course_key}')

        LOGGER.info('[Populate Course Duration] Execution completed.')
