from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied


class VerticalTaggingAdministratorPermissionRequiredMixin(LoginRequiredMixin):
    """
    A mixin to enforce permission on VERTICALS_MANAGEMENT_GROUPS for class-based views.
    """

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if response.status_code == 403:
            return response

        in_vertical_management_group = request.user.groups.filter(
            name__in=settings.VERTICALS_MANAGEMENT_GROUPS
        ).exists()

        if not request.user.is_superuser and not in_vertical_management_group:
            raise PermissionDenied("You do not have permission to access this page.")

        return response
