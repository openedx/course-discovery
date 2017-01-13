import logging

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail.message import EmailMultiAlternatives
from django.core.urlresolvers import reverse
from django.template.loader import get_template
from django.utils.translation import ugettext_lazy as _
from course_discovery.apps.publisher.choices import PublisherUserRole


logger = logging.getLogger(__name__)


def send_email_for_change_state(course_run):
    """ Send the emails for a course run change state event.

        Arguments:
            course_run (Object): CourseRun object
    """

    try:
        txt_template = 'publisher/email/change_state.txt'
        html_template = 'publisher/email/change_state.html'

        to_addresses = course_run.course.get_course_users_emails()
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

        subject = _('Course Run {title}-{pacing_type}-{start} state has been changed.').format(  # pylint: disable=no-member
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
        logger.exception('Failed to send email notifications for change state of course-run %s', course_run.id)


def send_email_for_studio_instance_created(course_run):
    """ Send an email to course team on studio instance creation.

        Arguments:
            course_run (CourseRun): CourseRun object
    """
    try:
        object_path = reverse('publisher:publisher_course_run_detail', kwargs={'pk': course_run.id})
        subject = _('Studio instance created')

        to_addresses = course_run.course.get_course_users_emails()
        from_address = settings.PUBLISHER_FROM_EMAIL

        course_user_roles = course_run.course.course_user_roles.all()
        course_team = course_user_roles.filter(role=PublisherUserRole.CourseTeam).first()
        partner_coordinator = course_user_roles.filter(role=PublisherUserRole.PartnerCoordinator).first()

        context = {
            'course_run': course_run,
            'course_run_page_url': 'https://{host}{path}'.format(
                host=Site.objects.get_current().domain.strip('/'), path=object_path
            ),
            'course_name': course_run.course.title,
            'from_address': from_address,
            'course_team_name': course_team.user.full_name if course_team else '',
            'partner_coordinator_name': partner_coordinator.user.full_name if partner_coordinator else '',
            'contact_us_email': partner_coordinator.user.email if partner_coordinator else ''
        }

        txt_template_path = 'publisher/email/studio_instance_created.txt'
        html_template_path = 'publisher/email/studio_instance_created.html'

        txt_template = get_template(txt_template_path)
        plain_content = txt_template.render(context)
        html_template = get_template(html_template_path)
        html_content = html_template.render(context)
        email_msg = EmailMultiAlternatives(
            subject, plain_content, from_address, to=[settings.PUBLISHER_FROM_EMAIL], bcc=to_addresses
        )
        email_msg.attach_alternative(html_content, 'text/html')
        email_msg.send()
    except Exception:  # pylint: disable=broad-except
        logger.exception('Failed to send email notifications for course_run [%s]', course_run.id)


def send_email_for_course_creation(course, course_run):
    """ Send the emails for a course creation.

        Arguments:
            course (Course): Course object
            course_run (CourseRun): CourseRun object
    """
    try:
        txt_template = 'publisher/email/course_created.txt'
        html_template = 'publisher/email/course_created.html'

        to_addresses = course.get_course_users_emails()
        from_address = settings.PUBLISHER_FROM_EMAIL

        course_user_roles = course_run.course.course_user_roles.all()
        course_team = course_user_roles.filter(role=PublisherUserRole.CourseTeam).first()
        partner_coordinator = course_user_roles.filter(role=PublisherUserRole.PartnerCoordinator).first()

        context = {
            'course_title': course_run.course.title,
            'date': course_run.created.strftime("%B %d, %Y"),
            'time': course_run.created.strftime("%H:%M:%S"),
            'course_team_name': course_team.user.full_name if course_team else '',
            'partner_coordinator_name': partner_coordinator.user.full_name if partner_coordinator else '',
            'dashboard_url': 'https://{host}{path}'.format(
                host=Site.objects.get_current().domain.strip('/'), path=reverse('publisher:publisher_dashboard')
            ),
            'from_address': from_address,
            'contact_us_email': partner_coordinator.user.email if partner_coordinator else ''
        }

        template = get_template(txt_template)
        plain_content = template.render(context)
        template = get_template(html_template)
        html_content = template.render(context)

        subject = _('New Studio instance request for {title}').format(title=course.title)  # pylint: disable=no-member

        email_msg = EmailMultiAlternatives(
            subject, plain_content, from_address, to=[settings.PUBLISHER_FROM_EMAIL], bcc=to_addresses
        )
        email_msg.attach_alternative(html_content, 'text/html')
        email_msg.send()
    except Exception:  # pylint: disable=broad-except
        logger.exception(
            'Failed to send email notifications for creation of course [%s]', course_run.course.id
        )
