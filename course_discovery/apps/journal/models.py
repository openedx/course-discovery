from django.db import models
from django_extensions.db.models import TimeStampedModel
from uuid import uuid4

from course_discovery.apps.core.models import Currency, Partner


class Journal(TimeStampedModel):
    """" Journal model """
    PRICE_FIELD_CONFIG = {
        'decimal_places': 2,
        'max_digits': 10,
        'null': False,
        'default': 0.00,
    }
    uuid = models.UUIDField(
        default=uuid4,
        editable=False,
        verbose_name='UUID',
    )
    partner = models.ForeignKey(Partner)
    key = models.CharField(max_length=255)
    title = models.CharField(
        max_length=225,
        default=None,
        null=True,
        blank=True
    )
    price = models.DecimalField(**PRICE_FIELD_CONFIG)
    currency = models.ForeignKey(Currency)
    sku = models.CharField(max_length=128, null=True, blank=True)
    expires = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return '{key}: {title}'.format(
            key=self.key,
            title=self.title
        )