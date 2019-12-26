import logging

from django.db import models
from django_comments.models import CommentAbstractModel
from django_extensions.db.fields import ModificationDateTimeField
from djchoices import ChoiceItem, DjangoChoices

log = logging.getLogger(__name__)


class CommentTypeChoices(DjangoChoices):
    Default = ChoiceItem('default', 'Default')
    Decline_Preview = ChoiceItem('decline_preview', 'Decline Preview')


class Comments(CommentAbstractModel):  # pylint: disable=model-no-explicit-unicode
    modified = ModificationDateTimeField('modified')
    comment_type = models.CharField(
        max_length=255, null=True, blank=True, choices=CommentTypeChoices.choices, default=CommentTypeChoices.Default
    )
