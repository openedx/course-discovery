from enum import Enum

COURSE_ID_REGEX = r'[^/+]+(/|\+)[^/+]+'
COURSE_RUN_ID_REGEX = r'[^/+]+(/|\+)[^/+]+(/|\+)[^/]+'
COURSE_SKILLS_URL_NAME = 'course_skills'
REFRESH_COURSE_SKILLS_URL_NAME = 'refresh_course_skills'
COURSE_UUID_REGEX = r'[0-9a-f-]+'

MASTERS_PROGRAM_TYPE_SLUG = 'masters'

IMAGE_TYPES = {
    'image/jpeg': 'jpg',
    'image/png': 'png',
}


class PathwayType(Enum):
    """ Allowed values for Pathway.pathway_type """
    CREDIT = 'credit'
    INDUSTRY = 'industry'
