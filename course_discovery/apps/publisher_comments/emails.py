import logging

from django.core.mail.message import EmailMultiAlternatives
from django.template.loader import get_template
from django.utils.translation import ugettext_lazy as _

from course_discovery.apps.publisher.models import CourseRun, Seat


log = logging.getLogger(__name__)


def setup_email_for_comment(comment):
    from course_discovery.apps.publisher.mixins import get_group_users_with_permission

    try:
        model_class = comment.content_type.model_class()
        publisher_obj = model_class.objects.filter(pk=comment.object_pk)[0]

        # Checking the permission on course object only.
        if model_class == CourseRun:
            course_obj = publisher_obj.course
            email_object_title = publisher_obj.lms_course_id
        elif model_class == Seat:
            course_obj = publisher_obj.course_run.course
            email_object_title = publisher_obj.course_run.lms_course_id
        else:
            course_obj = publisher_obj
            email_object_title = publisher_obj.title

        txt_template = 'publisher/emails/comments.txt'
        html_template = 'publisher/emails/comments.html'
        users_list = get_group_users_with_permission(comment.user, course_obj)
        to_addresses = [
            user.email for user in users_list
            if hasattr(user, 'attributes') and user.attributes.enable_notification
        ]
        from_address = 'info@edx.org'
        context = {
            'email_object_title': email_object_title,
            'comment': comment.comment,
            'user_info': comment.user.get_full_name() or comment.user.email
        }
        template = get_template(txt_template)
        plain_content = template.render(context)
        template = get_template(html_template)
        html_content = template.render(context)
        subject = _('New comment added.')
        email_msg = EmailMultiAlternatives(
            subject, plain_content, from_address, to_addresses
        )
        email_msg.attach_alternative(html_content, "text/html")
        email_msg.send()
    except:  # pylint: disable=bare-except
        log.error('Failed sending email for newly added comment.')
