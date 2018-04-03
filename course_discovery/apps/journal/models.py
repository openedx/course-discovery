from django.db import models
from django_extensions.db.models import TimeStampedModel
from django.utils.translation import ugettext_lazy as _
from uuid import uuid4

from course_discovery.apps.core.models import Currency, Partner
from course_discovery.apps.course_metadata.models import Course

CHARFIELD_MAX_LENGTH = 255


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
        verbose_name=_('UUID'),
    )
    partner = models.ForeignKey(Partner)
    title = models.CharField(
        max_length=CHARFIELD_MAX_LENGTH,
        default=None,
        null=True,
        blank=True
    )
    price = models.DecimalField(**PRICE_FIELD_CONFIG)
    currency = models.ForeignKey(Currency)
    sku = models.CharField(max_length=128, null=True, blank=True)
    expires = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = (
            ('partner', 'uuid')
        )
        ordering = ('created',)

    def __str__(self):
        return self.title


class JournalBundle(TimeStampedModel):
    """ Journal Bundle Model """
    uuid = models.UUIDField(
        default=uuid4,
        editable=False,
        verbose_name=_('UUID')
    )
    title = models.CharField(
        help_text=_('The user-facing display title for this Journal Bundle'),
        max_length=CHARFIELD_MAX_LENGTH,
        unique=True
    )
    partner = models.ForeignKey(Partner)
    journals = models.ManyToManyField(Journal, blank=True)
    courses = models.ManyToManyField(Course, blank=True)

    def __str__(self):
        return self.title
