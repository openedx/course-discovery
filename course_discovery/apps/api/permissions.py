from rest_framework.permissions import BasePermission


class ReadOnlyByPublisherUser(BasePermission):
    """
    Custom Permission class to check user is a publisher user.
    """
    def has_permission(self, request, view):
        if request.method == 'GET':
            return request.user.groups.exists()
        return True


class WriteOnlyByStaffUser(BasePermission):
    """
    Custom Permission class to check user is an admin to write.
    """
    def has_permission(self, request, view):
        if request.method == 'POST' or request.method == 'PUT' or request.method == 'PATCH':
            return request.user.is_staff
        return True
