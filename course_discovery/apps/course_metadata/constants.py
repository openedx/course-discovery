COURSE_ID_REGEX = r'[^/+]+(/|\+)[^/+]+'
COURSE_RUN_ID_REGEX = r'[^/+]+(/|\+)[^/+]+(/|\+)[^/]+'


class ProgramCategory(object):
    """Allowed values for Program.category"""

    XSERIES = "xseries"


class ProgramStatus(object):
    """Allowed values for Program.status"""

    UNPUBLISHED = "unpublished"
    ACTIVE = "active"
    RETIRED = "retired"
    DELETED = "deleted"
