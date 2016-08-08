from django.utils.translation import ugettext_lazy as _

from django_comments.models import CommentAbstractModel
from django_extensions.db.fields import ModificationDateTimeField


class Comments(CommentAbstractModel):
    modified = ModificationDateTimeField(_('modified'))
