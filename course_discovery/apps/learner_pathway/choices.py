from django.db import models
from django.utils.translation import gettext_lazy as _


class PathwayStatus(models.TextChoices):
    Active = 'active', _('Active')
    Inactive = 'inactive', _('Inactive')
