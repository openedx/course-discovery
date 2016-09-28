from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import ugettext_lazy as _
from django_comments.models import CommentAbstractModel
from django_extensions.db.fields import ModificationDateTimeField

import waffle


class Comments(CommentAbstractModel):
    modified = ModificationDateTimeField(_('modified'))


@receiver(post_save, sender=Comments)
def send_email(sender, instance, **kwargs):    # pylint: disable=unused-argument
    """ Send email on new comment. """
    if waffle.switch_is_active('enable_emails'):
        from django.core.mail import send_mail
        send_mail(
            'Subject here',
            'Here is the message.',
            'awais@edx.org',
            ['awais@edx.org'],
            fail_silently=False,
        )
