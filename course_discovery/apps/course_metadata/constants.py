from enum import Enum

COURSE_ID_REGEX = r'[^/+]+(/|\+)[^/+]+'
COURSE_RUN_ID_REGEX = r'[^/+]+(/|\+)[^/+]+(/|\+)[^/]+'
COURSE_SKILLS_URL_NAME = 'course_skills'
REFRESH_COURSE_SKILLS_URL_NAME = 'refresh_course_skills'
REFRESH_PROGRAM_SKILLS_URL_NAME = 'refresh_program_skills'
COURSE_UUID_REGEX = r'[0-9a-f-]+'

MASTERS_PROGRAM_TYPE_SLUG = 'masters'

IMAGE_TYPES = {
    'image/jpeg': 'jpg',
    'image/png': 'png',
    'image/svg+xml': 'svg'  # SVG image will be converted into PNG, not stored as SVG
}

ALLOWED_ANCHOR_TAG_ATTRIBUTES = ['href', 'title', 'target', 'rel']

DRIVE_LINK_PATTERNS = [r"https://docs\.google\.com/uc\?id=\w+",
                       r"https://drive\.google\.com/file/d/\w+/view?usp=sharing"]

GOOGLE_CLIENT_API_SCOPE = ['https://www.googleapis.com/auth/drive.readonly']


class PathwayType(Enum):
    """ Allowed values for Pathway.pathway_type """
    CREDIT = 'credit'
    INDUSTRY = 'industry'


SNOWFLAKE_POPULATE_COURSE_LENGTH_QUERY = '''
    WITH completions as (

    /* Get all completions, all time.
    */

    SELECT
        ccu.user_id,
        dc.course_uuid,
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
        completions.course_uuid,
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
        course_uuid,
        round(AVG(hours_of_learning),1) as avg_pass_time,
        COUNT(*) as n_passed_learners
    FROM
        time_to_pass
    GROUP BY
        1
    )

    select
        course_uuid,
        avg_pass_time,
        case when avg_pass_time <= 6.5 then 'short'
        when avg_pass_time < 13 then 'medium'
        when avg_pass_time >= 13 then 'long'
        end as course_length_bin
    from
        courses
'''


SNOWFLAKE_REFRESH_COURSE_REVIEWS_QUERY = '''
    select
        COURSE_KEY,
        REVIEWS_COUNT,
        AVG_COURSE_RATING,
        CONFIDENT_LEARNERS_PERCENTAGE,
        MOST_COMMON_GOAL,
        MOST_COMMON_GOAL_LEARNERS_PERCENTAGE,
        TOTAL_ENROLLMENTS_IN_LAST_12_MONTHS
    from
        prod.enterprise.course_reviews
'''
