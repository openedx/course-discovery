from rest_framework.permissions import BasePermission


class ReadByStaffOnly(BasePermission):
    """
    Custom permission to only allow owners of the object.
    """
    def has_permission(self, request, view):
        if request.method == 'GET':
                return request.user.is_staff
        return True
