from enum import Enum

COURSE_ID_REGEX = r'[^/+]+(/|\+)[^/+]+'
COURSE_RUN_ID_REGEX = r'[^/+]+(/|\+)[^/+]+(/|\+)[^/]+'
COURSE_SKILLS_URL_NAME = 'course_skills'
REFRESH_COURSE_SKILLS_URL_NAME = 'refresh_course_skills'
REFRESH_PROGRAM_SKILLS_URL_NAME = 'refresh_program_skills'
COURSE_UUID_REGEX = r'[0-9a-f-]+'
SUBDIRECTORY_SLUG_FORMAT_REGEX = (
    r'learn\/[a-zA-Z0-9-_]+\/[a-zA-Z0-9-_]+$|'
    r'executive-education\/[a-zA-Z0-9-_]+$|'
    r'boot-camps\/[a-zA-Z0-9-_]+\/[a-zA-Z0-9-_]+$'
)
SUBDIRECTORY_PROGRAM_SLUG_FORMAT_REGEX = r'[a-zA-Z0-9-_]+\/[a-zA-Z0-9-_\/]+$'
PROGRAM_SLUG_FORMAT_REGEX = r'[a-zA-Z0-9-_]+'

SLUG_FORMAT_REGEX = r'[a-zA-Z0-9-_]+$'

DEFAULT_SLUG_FORMAT_ERROR_MSG = 'Enter a valid “slug” consisting of letters, numbers, underscores or hyphens.'

MASTERS_PROGRAM_TYPE_SLUG = 'masters'

IMAGE_TYPES = {
    'image/jpeg': 'jpg',
    'image/png': 'png',
    'image/svg+xml': 'svg',  # SVG image will be converted into PNG, not stored as SVG
    'application/binary': 'jpg',  # Dropbox binary images are downloaded as JPG
}

ALLOWED_ANCHOR_TAG_ATTRIBUTES = ['href', 'title', 'target', 'rel']
ALLOWED_PARAGRAPH_TAG_ATTRIBUTES = ['dir', 'lang']
HTML_TAGS_ATTRIBUTE_WHITELIST = {
    'a': ALLOWED_ANCHOR_TAG_ATTRIBUTES,
    'p': ALLOWED_PARAGRAPH_TAG_ATTRIBUTES,
}

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

COURSE_TYPES = {
    'ocm_course' : ['audit', 'verified-audit', 'verified', 'credit-verified-audit', 'spoc-verified-audit', 'professional'],
    'executive_education' : ['executive-education-2u'],
    'bootcamp' : ['bootcamp-2u'],
}

SNOWFLAKE_POPULATE_PRODUCT_COURSES_CATALOG_QUERY = """
    WITH course_data AS (
    SELECT 
        c.id, c.uuid as COURSE_UUID, 
        c.key as COURSE_KEY,
        cr.key as COURSERUN_KEY,
        c.title AS COURSE_TITLE,
        coursetype.name AS COURSE_TYPE,
        COUNT(DISTINCT org.id) AS ORGANIZATIONS_COUNT,
        LISTAGG(DISTINCT org.key, ', ') AS ORGANISATION_ABBR,
        LISTAGG(DISTINCT org.name, ', ') AS ORGANIZATION_NAME,
        LISTAGG(DISTINCT CONCAT('{DISCOVERY_CDN_URL}', org.logo_image), ', ') AS ORGANIZATION_LOGO,
        COUNT(DISTINCT cr.language_id) AS languagesCount,
        LISTAGG(DISTINCT cr.language_id, ', ') AS Languages,
        LISTAGG(DISTINCT CASE WHEN st.language_code <> 'es' THEN st.name ELSE NULL END, ', ') AS Subjects,
        LISTAGG(DISTINCT CASE WHEN st.language_code = 'es' THEN st.name ELSE NULL END, ', ') AS Subject_Spanish,
        LISTAGG(DISTINCT s.type, ', ') AS SEAT_TYPE, 
        CONCAT(p.marketing_site_url_root, cslug.url_Slug) AS MARKETING_URL,
        CASE
            WHEN c.image IS NOT NULL THEN CONCAT('{DISCOVERY_CDN_URL}', c.image)
            ELSE CONCAT('{DISCOVERY_CDN_URL}', c.card_image_url)
        END AS MARKETING_IMAGE,
        CASE
            WHEN cr.RUN_START IS NOT NULL AND cr.RUN_START >= CURRENT_TIMESTAMP() THEN 'True'
            ELSE 'False'
        END AS is_upcoming,
        CASE
            WHEN (cr.enrollment_end IS NULL OR cr.enrollment_end >= CURRENT_TIMESTAMP()) AND (cr.enrollment_start IS NULL OR cr.enrollment_start <= CURRENT_TIMESTAMP()) THEN 'True'
            ELSE 'False'
        END AS is_enrollable,
        CASE
            WHEN crt.is_marketable = TRUE 
                AND cr.draft = FALSE 
                AND cr.status = 'published'
                AND s.id IS NOT NULL  -- Checking if there are any seats
                AND (cr.slug IS NOT NULL AND cr.slug != '' AND crt.is_marketable = TRUE) -- is_marketable 
            THEN 'True'
            ELSE 'False'
        END AS is_marketable,
        CASE
            WHEN cr.RUN_END IS NOT NULL AND cr.RUN_END < CURRENT_TIMESTAMP() THEN 'True'
            ELSE 'False'
        END AS has_ended,
        LISTAGG(DISTINCT 
            CASE
                WHEN cr.RUN_END < CURRENT_TIMESTAMP() THEN 'Archived'
                WHEN cr.RUN_START <= CURRENT_TIMESTAMP() THEN 'Current'
                WHEN cr.RUN_START < DATEADD(DAY, 60, CURRENT_TIMESTAMP()) THEN 'Starting Soon'
                ELSE 'Upcoming'
            END, ', ') AS availability_status,
        LISTAGG(cr.pacing_type, ', ') AS pacing
    FROM 
        discovery.course_metadata_courserun AS cr
    JOIN 
        discovery.course_metadata_course AS c ON c.id = cr.course_id 
    JOIN 
        discovery.core_partner AS p ON c.partner_id = p.id
    JOIN 
        discovery.course_metadata_courseruntype AS crt ON crt.id = cr.type_id
    JOIN
        discovery.course_metadata_seat AS s ON cr.id = s.course_run_id
    JOIN
        discovery.course_metadata_coursetype AS coursetype ON coursetype.id = c.type_id
    JOIN 
        discovery.course_metadata_course_authoring_organizations AS cao ON c.id = cao.course_id
    JOIN 
        discovery.course_metadata_organization AS org ON cao.organization_id = org.id 
    JOIN 
        discovery.course_metadata_course_subjects AS cs ON c.id = cs.course_id
    JOIN 
        discovery.course_metadata_subject AS sb ON sb.id = cs.subject_id
    JOIN 
        discovery.course_metadata_subjecttranslation AS st ON st.master_id = sb.id 
    JOIN
        discovery.course_metadata_courseurlslug AS cslug ON c.id = cslug.course_id
    JOIN
        discovery.course_metadata_source as product_source on c.product_source_id = product_source.id
    WHERE 
        c.draft != 1 AND cr.hidden != 1 AND cr.status = 'published'
        AND coursetype.slug IN ( {course_types} )
        AND cslug.is_active = 1 {product_source_filter}
    GROUP BY 
        c.uuid, c.id, c.key, cr.key, c.title, coursetype.name, p.marketing_site_url_root, cslug.url_Slug, c.image, c.card_image_url, cr.RUN_START, cr.enrollment_end, cr.enrollment_start, cr.RUN_END, crt.is_marketable, cr.draft, cr.status, s.id, cr.slug
    ORDER BY 
        c.id
    )
    SELECT DISTINCT COURSE_UUID, COURSE_TITLE, ORGANIZATION_NAME, ORGANIZATION_LOGO, ORGANISATION_ABBR, Languages, Subjects, Subject_Spanish, MARKETING_URL, MARKETING_IMAGE, COURSE_TYPE
    FROM course_data
    WHERE 
        (is_upcoming = 'True') 
        OR (is_enrollable = 'True' AND has_ended != 'True' AND is_marketable = 'True');
"""

SNOWFLAKE_POPULATE_PRODUCT_DEGREES_CATALOG_QUERY = """
    SELECT 
        cmp.uuid,
        cmp.title,
        COALESCE(
            LISTAGG(DISTINCT cmo.name, ', '),
            ''
        ) AS authoring_organizations,
        COALESCE(
            LISTAGG(DISTINCT CONCAT('{DISCOVERY_CDN_URL}', cmo.logo_image), ', '), ''
        ) AS authoring_organizations_logo,
        COALESCE(
            LISTAGG(DISTINCT cmo.key, ', '), ''
        ) AS authoring_organizations_abbr,
        CASE
            -- First, check if there is a language override and it's not empty
            WHEN cmp.language_override_id IS NOT NULL AND cmp.language_override_id <> '' 
            THEN cmp.language_override_id
            -- If no override, check if there are course run languages
            WHEN COUNT(DISTINCT cr.language_id) > 0 
            THEN LISTAGG(DISTINCT cr.language_id, ', ')
            -- Default value if no language is found
            ELSE 'en-us'
        END AS languages,
        LISTAGG(DISTINCT CASE WHEN st.language_code <> 'es' THEN st.name ELSE NULL END, ', ') AS Primary_Subject,
        LISTAGG(DISTINCT CASE WHEN st.language_code = 'es' THEN st.name ELSE NULL END, ', ') AS Primary_Subject_Spanish,
        CASE
            WHEN POSITION('/', cmp.marketing_slug) = 0 THEN CONCAT(
                cp.marketing_site_url_root,
                cmpt.slug,
                '/',
                cmp.marketing_slug
            )
            ELSE CONCAT(cp.marketing_site_url_root, cmp.marketing_slug)
        END AS marketing_url,
        CASE 
            WHEN cmp.card_image = '' OR cmp.card_image IS NULL 
            THEN '' 
            ELSE CONCAT('{DISCOVERY_CDN_URL}', cmp.card_image) 
        END AS MARKETING_IMAGE,
        CONCAT_WS(
            ', ',
            cms_primary.slug,
            LISTAGG(DISTINCT cms.slug, ', ')
        ) AS subjects,
        CASE
            WHEN cmd.program_ptr_id IS NULL THEN 0
            ELSE 1
        END AS is_degree,
        cmp.status,

    FROM discovery.course_metadata_program cmp
        INNER JOIN discovery.core_partner cp ON cp.id = cmp.partner_id
        INNER JOIN discovery.course_metadata_programtype cmpt ON cmpt.id = cmp.type_id
        LEFT JOIN discovery.course_metadata_degree cmd ON cmp.id = cmd.program_ptr_id
        LEFT JOIN discovery.course_metadata_degreeadditionalmetadata cmdam ON cmd.program_ptr_id = cmdam.degree_id
        LEFT JOIN discovery.course_metadata_program_authoring_organizations cmpao ON cmpao.program_id = cmp.id
        LEFT JOIN discovery.course_metadata_organization cmo ON cmo.id = cmpao.organization_id
        LEFT JOIN discovery.course_metadata_program_courses cmpc ON cmpc.program_id = cmp.id
        LEFT JOIN discovery.course_metadata_course cmc ON cmc.id = cmpc.course_id
        LEFT JOIN COURSE_METADATA_courserun cr ON cr.course_id = cmc.id 
        LEFT JOIN discovery.course_metadata_course_subjects cmcs ON cmcs.course_id = cmc.id
        LEFT JOIN discovery.course_metadata_subject cms ON cms.id = cmcs.subject_id
        LEFT JOIN discovery.course_metadata_subject cms_primary ON cms_primary.id = cmp.primary_subject_override_id
        LEFT JOIN discovery.course_metadata_subjecttranslation AS st ON st.master_id = cmp.primary_subject_override_id or st.master_id = cmcs.subject_id
        LEFT JOIN discovery.course_metadata_source as product_source on product_source.id = cmp.product_source_id
        WHERE cmp.partner_id = 1 and cmp.status = 'active' {product_source_filter}
        GROUP BY 
            cmp.uuid,
            cmp.title,
            cmp.status,
            cmp.marketing_slug,
            cmpt.slug,
            cp.name,
            cmd.program_ptr_id,
            cp.marketing_site_url_root,
            cms_primary.slug, -- Added cms_primary.slug to the GROUP BY clause
            cmp.language_override_id,
            cmp.card_image
        HAVING 
            IS_DEGREE = 1;
"""
SNOWFLAKE_POPULATE_PRODUCT_CATALOG_QUERY = {
    'course' : SNOWFLAKE_POPULATE_PRODUCT_COURSES_CATALOG_QUERY,
    'degree': SNOWFLAKE_POPULATE_PRODUCT_DEGREES_CATALOG_QUERY,
}
