import logging

from rest_framework import permissions

logger = logging.getLogger(__name__)


class UserHasGroup(permissions.BasePermission):
    """
    Global permission to check if request.user has any group
    """
    def has_permission(self, request, view):
        if request.user.groups.all():
            return True
        logger.info('Permission denied. User [%s] has no groups', request.user.username)
        return False
