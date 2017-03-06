import logging
import waffle
from django.db import models, transaction
from django.utils.translation import ugettext_lazy as _
from django_comments.models import CommentAbstractModel
from django_extensions.db.fields import ModificationDateTimeField
from djchoices import ChoiceItem, DjangoChoices

from course_discovery.apps.publisher.choices import PublisherUserRole
from course_discovery.apps.publisher_comments.emails import send_email_decline_preview, send_email_for_comment

log = logging.getLogger(__name__)


class CommentTypeChoices(DjangoChoices):
    Default = ChoiceItem('default', _('Default'))
    Decline_Preview = ChoiceItem('decline_preview', _('Decline Preview'))


class Comments(CommentAbstractModel):
    DEFAULT = 'default'
    DECLINE_PREVIEW = 'decline_preview'

    modified = ModificationDateTimeField(_('modified'))

    # comment type added to differentiate weather comment is for preview decline or a
    # normal comment on content of course/course run.
    comment_type = models.CharField(
        max_length=255, null=True, blank=True, choices=CommentTypeChoices.choices, default=CommentTypeChoices.Default
    )

    def save(self, *args, **kwargs):
        if self.comment_type == CommentTypeChoices.Decline_Preview:
            try:
                mark_preview_url_as_decline(self)
            except Exception:  # pylint: disable=broad-except
                # in case of exception don't save the comment
                return
        else:
            if waffle.switch_is_active('enable_publisher_email_notifications'):
                created = False if self.id else True
                send_email_for_comment(self, created)

        super(Comments, self).save(*args, **kwargs)


@transaction.atomic
def mark_preview_url_as_decline(instance):
    course_run = instance.content_type.get_object_for_this_type(pk=instance.object_pk)

    # remove the preview url
    preview_url = course_run.preview_url
    course_run.preview_url = None
    course_run.save()

    # assign course back to publisher
    course_run.course_run_state.change_owner_role(PublisherUserRole.Publisher)

    # send email for decline preview to publisher
    if waffle.switch_is_active('enable_publisher_email_notifications'):
        send_email_decline_preview(instance, course_run, preview_url)
