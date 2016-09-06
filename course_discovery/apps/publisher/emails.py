import logging

from django.core.mail.message import EmailMultiAlternatives
from django.template.loader import get_template
from django.utils.translation import ugettext_lazy as _


log = logging.getLogger(__name__)


def setup_email_for_state(course_run):
    from course_discovery.apps.publisher.mixins import get_group_users_with_permission
    try:
        changed_by_user = course_run.state.changed_by
        txt_template = 'publisher/emails/change_state.txt'
        html_template = 'publisher/emails/change_state.html'
        users_list = get_group_users_with_permission(changed_by_user, course_run.course)
        to_addresses = [
            user.email for user in users_list
            if hasattr(user, 'attributes') and user.attributes.enable_notification
        ]
        from_address = 'info@edx.org'
        context = {
            'course_id': course_run.lms_course_id,
            'state_name': course_run.current_state,
            'user_info': changed_by_user.get_full_name() or changed_by_user.email
        }
        template = get_template(txt_template)
        plain_content = template.render(context)
        template = get_template(html_template)
        html_content = template.render(context)
        subject = _('Course run state has changed.')
        email_msg = EmailMultiAlternatives(
            subject, plain_content, from_address, to_addresses
        )
        email_msg.attach_alternative(html_content, "text/html")
        email_msg.send()
    except:  # pylint: disable=bare-except
        log.error('Failed sending status change e-mail for course.')
