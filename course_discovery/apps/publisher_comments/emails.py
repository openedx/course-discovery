import logging

from django.conf import settings
from django.core.mail.message import EmailMultiAlternatives
from django.core.urlresolvers import reverse
from django.template.loader import get_template
from django.utils.translation import ugettext_lazy as _

from course_discovery.apps.publisher.models import CourseRun
from course_discovery.apps.publisher.utils import is_email_notification_enabled

log = logging.getLogger(__name__)


def send_email_for_comment(comment, created=False):
    """ Send the emails for a comment.

        Arguments:
            comment (Comment): Comment object
            created (Bool): Value indicating comment is created or updated
    """
    try:
        object_pk = comment.object_pk
        publisher_obj = comment.content_type.get_object_for_this_type(pk=object_pk)
        comment_class = comment.content_type.model_class()

        subject_desc = _('New comment added')

        if not created:
            subject_desc = _('Comment updated')

        if comment_class == CourseRun:
            course = publisher_obj.course
            object_path = reverse('publisher:publisher_course_run_detail', args=[publisher_obj.id])

            # Translators: subject_desc will be choice from ('New comment added', 'Comment updated'),
            # 'pacing_type' will be choice from ('instructor-paced', 'self-paced'),
            # 'title' and 'start' will be the value of course title & start date fields.
            subject = _('{subject_desc} in course run: {title}-{pacing_type}-{start}').format(  # pylint: disable=no-member
                subject_desc=subject_desc,
                title=course.title,
                pacing_type=publisher_obj.get_pacing_type_display(),
                start=publisher_obj.start.strftime('%B %d, %Y') if publisher_obj.start else ''
            )
        else:
            course = publisher_obj
            object_path = reverse('publisher:publisher_courses_edit', args=[publisher_obj.id])

            # Translators: 'subject_desc' will be choice from ('New comment added', 'Comment updated')
            # and 'title' will be the value of course title field.
            subject = _('{subject_desc} in Course: {title}').format(  # pylint: disable=no-member
                subject_desc=subject_desc,
                title=course.title
            )

        to_addresses = course.get_course_users_emails()
        from_address = settings.PUBLISHER_FROM_EMAIL

        context = {
            'comment': comment,
            'course': course,
            'object_type': comment_class.__name__,
            'page_url': 'https://{host}{path}'.format(host=comment.site.domain.strip('/'), path=object_path)
        }

        txt_template = 'publisher/email/comment.txt'
        html_template = 'publisher/email/comment.html'

        template = get_template(txt_template)
        plain_content = template.render(context)
        template = get_template(html_template)
        html_content = template.render(context)
        email_msg = EmailMultiAlternatives(
            subject, plain_content, from_address, to_addresses
        )
        email_msg.attach_alternative(html_content, 'text/html')
        email_msg.send()
    except Exception:  # pylint: disable=broad-except
        log.exception('Failed to send email notifications for comment %s', comment.id)


def send_email_decline_preview(comment, course_run, preview_url):
    """ Send the emails for a comment for decline preview.

        Arguments:
            comment (Comment): Comment object
            course_run (CourseRun): course-run object
            preview_url (url): preview_url
    """
    try:
        object_path = reverse('publisher:publisher_course_run_detail', args=[course_run.id])

        # Translators: subject_desc will be Preview Decline for course run,
        # 'title' will be the value of course title.
        subject = _('Preview Decline for course run: {title}').format(  # pylint: disable=no-member
            title=course_run.course.title
        )

        recipient_user = course_run.course.publisher
        if is_email_notification_enabled(recipient_user):
            to_addresses = [recipient_user.email]

            from_address = settings.PUBLISHER_FROM_EMAIL
            context = {
                'comment': comment,
                'page_url': 'https://{host}{path}'.format(host=comment.site.domain.strip('/'), path=object_path),
                'preview_url': preview_url,
                'course_title': course_run.course.title,
            }

            txt_template = 'publisher/email/decline_preview.txt'
            html_template = 'publisher/email/decline_preview.html'

            template = get_template(txt_template)
            plain_content = template.render(context)
            template = get_template(html_template)
            html_content = template.render(context)
            email_msg = EmailMultiAlternatives(
                subject, plain_content, from_address, to_addresses
            )
            email_msg.attach_alternative(html_content, 'text/html')
            email_msg.send()
    except Exception:  # pylint: disable=broad-except
        message = 'Failed to send email notifications for preview decline for course run [{id}].'.format(
            id=course_run.id
        )
        log.exception(message)
        raise Exception(message)
