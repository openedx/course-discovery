"""
Programs API constants.
"""
from __future__ import unicode_literals


class ProgramCategory(object):
    """Allowed values for Program.category"""

    XSERIES = "xseries"


class ProgramStatus(object):
    """Allowed values for Program.status"""

    UNPUBLISHED = "unpublished"
    ACTIVE = "active"
    RETIRED = "retired"
    DELETED = "deleted"
