from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


class VerticalTaggingAdministratorPermissionRequiredMixin(
    LoginRequiredMixin, UserPassesTestMixin
):
    """
    A mixin to enforce permission on VERTICALS_MANAGEMENT_GROUPS for class-based views.
    """

    def test_func(self):
        """
        Check if the user is in the VERTICALS_MANAGEMENT_GROUPS group or is a superuser.
        """
        return self.request.user.is_superuser or self.request.user.groups.filter(
            name__in=settings.VERTICALS_MANAGEMENT_GROUPS
        ).exists()
