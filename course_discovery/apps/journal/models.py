from django.db import models
from django_extensions.db.models import TimeStampedModel
from django.utils.translation import ugettext_lazy as _
from uuid import uuid4

from course_discovery.apps.core.models import Currency, Partner
from course_discovery.apps.course_metadata.models import Course, Organization, SeatType
from course_discovery.apps.journal.choices import JournalStatus

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
        verbose_name=_('UUID'),
    )
    partner = models.ForeignKey(Partner)
    organization = models.ForeignKey(Organization)
    title = models.CharField(
        max_length=CHARFIELD_MAX_LENGTH,
        default=None,
        null=True,
        blank=True
    )

    # ecommerce related
    price = models.DecimalField(**PRICE_FIELD_CONFIG)
    currency = models.ForeignKey(Currency)
    sku = models.CharField(max_length=128, null=True, blank=True)

    # marketing related fields
    card_image_url = models.URLField(null=True, blank=True)
    short_description = models.CharField(max_length=350, default=None, null=False)
    full_description = models.TextField(default=None, null=True, blank=True)
    access_length = models.IntegerField(null=True, help_text='number of days valid after purchase', default=365)
    status = models.CharField(
        help_text=_('Used to determine whether journal is marketed or not.'), max_length=24, null=False, blank=False, db_index=True,
        choices=JournalStatus.choices, validators=[JournalStatus.validator], default=JournalStatus.Active
    )

    class Meta:
        unique_together = (
            ('partner', 'uuid'),
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
    applicable_seat_types = models.ManyToManyField(SeatType, blank=True)

    def __str__(self):
        return self.title
