"""
Permissions for Edly Sites API.
"""
import logging

from django.conf import settings
from rest_framework import permissions

logger = logging.getLogger(__name__)


class CanAccessSiteCreation(permissions.BasePermission):
    """
    Checks if a user has the access to create and update methods for sites.
    """

    def has_permission(self, request, view):
        """
        Checks for user's permission for current site.
        """
        return request.user.is_staff or request.user.username == settings.EDLY_PANEL_WORKER_USER
