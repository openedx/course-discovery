from enum import Enum

COURSE_ID_REGEX = r'[^/+]+(/|\+)[^/+]+'
COURSE_RUN_ID_REGEX = r'[^/+]+(/|\+)[^/+]+(/|\+)[^/]+'
COURSE_UUID_REGEX = r'[0-9a-f-]+'

MASTERS_PROGRAM_TYPE_SLUG = 'masters'


class PathwayType(Enum):
    """ Allowed values for Pathway.pathway_type """
    CREDIT = 'credit'
    INDUSTRY = 'industry'
