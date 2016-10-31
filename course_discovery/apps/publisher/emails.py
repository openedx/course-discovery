import logging

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail.message import EmailMultiAlternatives
from django.core.urlresolvers import reverse
from django.template.loader import get_template
from django.utils.translation import ugettext_lazy as _


log = logging.getLogger(__name__)


def send_email_for_change_state(course_run):
    """ Send the emails for a comment.

        Arguments:
            course_run (Object): CourseRun object
    """

    try:
        txt_template = 'publisher/email/change_state.txt'
        html_template = 'publisher/email/change_state.html'

        to_addresses = course_run.course.get_group_users_emails()
        from_address = settings.PUBLISHER_FROM_EMAIL
        page_path = reverse('publisher:publisher_course_run_detail', kwargs={'pk': course_run.id})
        context = {
            'state_name': course_run.current_state,
            'course_run_page_url': 'https://{host}{path}'.format(
                host=Site.objects.get_current().domain.strip('/'), path=page_path
            )
        }
        template = get_template(txt_template)
        plain_content = template.render(context)
        template = get_template(html_template)
        html_content = template.render(context)

        subject = _('Course Run {title}-{pacing_type}-{start} state has been changed.').format(
            title=course_run.course.title,
            pacing_type=course_run.get_pacing_type_display(),
            start=course_run.start.strftime('%B %d, %Y') if course_run.start else ''
        )

        email_msg = EmailMultiAlternatives(
            subject, plain_content, from_address, to_addresses
        )
        email_msg.attach_alternative(html_content, 'text/html')
        email_msg.send()
    except Exception:  # pylint: disable=broad-except
        log.exception('Failed to send email notifications for change state of course-run %s', course_run.id)
