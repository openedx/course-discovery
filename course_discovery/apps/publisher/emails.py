import logging

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail.message import EmailMultiAlternatives
from django.core.urlresolvers import reverse
from django.template.loader import get_template
from django.utils.translation import ugettext_lazy as _

from course_discovery.apps.publisher.choices import PublisherUserRole
from course_discovery.apps.publisher.utils import is_email_notification_enabled

logger = logging.getLogger(__name__)


def send_email_for_studio_instance_created(course_run, updated_text=_('created')):
    """ Send an email to course team on studio instance creation.

        Arguments:
            course_run (CourseRun): CourseRun object
            updated_text (String): String object
    """
    try:
        object_path = reverse('publisher:publisher_course_run_detail', kwargs={'pk': course_run.id})
        subject = _('Studio instance {updated_text}').format(updated_text=updated_text)     # pylint: disable=no-member

        to_addresses = course_run.course.get_course_users_emails()
        from_address = settings.PUBLISHER_FROM_EMAIL

        course_user_roles = course_run.course.course_user_roles.all()
        course_team = course_user_roles.filter(role=PublisherUserRole.CourseTeam).first()
        project_coordinator = course_user_roles.filter(role=PublisherUserRole.ProjectCoordinator).first()

        context = {
            'updated_text': updated_text,
            'course_run': course_run,
            'course_run_page_url': 'https://{host}{path}'.format(
                host=Site.objects.get_current().domain.strip('/'), path=object_path
            ),
            'course_name': course_run.course.title,
            'from_address': from_address,
            'course_team_name': course_team.user.full_name if course_team else '',
            'project_coordinator_name': project_coordinator.user.full_name if project_coordinator else '',
            'contact_us_email': project_coordinator.user.email if project_coordinator else ''
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
    txt_template = 'publisher/email/course_created.txt'
    html_template = 'publisher/email/course_created.html'

    subject = _('New Studio instance request for {title}').format(title=course.title)  # pylint: disable=no-member
    project_coordinator = course.project_coordinator
    course_team = course.course_team_admin

    if is_email_notification_enabled(project_coordinator):
        try:
            to_addresses = [project_coordinator.email]
            from_address = settings.PUBLISHER_FROM_EMAIL

            context = {
                'course_title': course_run.course.title,
                'date': course_run.created.strftime("%B %d, %Y"),
                'time': course_run.created.strftime("%H:%M:%S"),
                'course_team_name': course_team.get_full_name(),
                'project_coordinator_name': project_coordinator.get_full_name(),
                'dashboard_url': 'https://{host}{path}'.format(
                    host=Site.objects.get_current().domain.strip('/'), path=reverse('publisher:publisher_dashboard')
                ),
                'from_address': from_address,
                'contact_us_email': project_coordinator.email
            }

            template = get_template(txt_template)
            plain_content = template.render(context)
            template = get_template(html_template)
            html_content = template.render(context)

            email_msg = EmailMultiAlternatives(
                subject, plain_content, from_address, to=to_addresses
            )
            email_msg.attach_alternative(html_content, 'text/html')
            email_msg.send()
        except Exception:  # pylint: disable=broad-except
            logger.exception(
                'Failed to send email notifications for creation of course [%s]', course_run.course.id
            )


def send_email_for_send_for_review(course, user):
    """ Send email when course is submitted for review.

        Arguments:
            course (Object): Course object
            user (Object): User object
    """
    txt_template = 'publisher/email/course/send_for_review.txt'
    html_template = 'publisher/email/course/send_for_review.html'
    subject = _('Changes to {title} are ready for review').format(title=course.title)  # pylint: disable=no-member

    try:
        page_path = reverse('publisher:publisher_course_detail', kwargs={'pk': course.id})
        send_course_workflow_email(course, user, subject, txt_template, html_template, page_path)
    except Exception:  # pylint: disable=broad-except
        logger.exception('Failed to send email notifications send for review of course %s', course.id)


def send_email_for_mark_as_reviewed(course, user):
    """ Send email when course is marked as reviewed.

        Arguments:
            course (Object): Course object
            user (Object): User object
    """
    txt_template = 'publisher/email/course/mark_as_reviewed.txt'
    html_template = 'publisher/email/course/mark_as_reviewed.html'
    subject = _('Changes to {title} has been approved').format(title=course.title)  # pylint: disable=no-member

    try:
        page_path = reverse('publisher:publisher_course_detail', kwargs={'pk': course.id})
        send_course_workflow_email(course, user, subject, txt_template, html_template, page_path)
    except Exception:  # pylint: disable=broad-except
        logger.exception('Failed to send email notifications mark as reviewed of course %s', course.id)


def send_course_workflow_email(course, user, subject, txt_template, html_template, page_path, course_name=None):
    """ Send email for course workflow state change.

        Arguments:
            course (Object): Course object
            user (Object): User object
            subject (String): Email subject
            txt_template: (String): Email text template path
            html_template: (String): Email html template path
            page_path: (URL): Detail page url
            course_name: (String): Custom course name, by default None
    """
    recipient_user = course.marketing_reviewer
    user_role = course.course_user_roles.get(user=user)
    if user_role.role == PublisherUserRole.MarketingReviewer:
        recipient_user = course.course_team_admin

    if is_email_notification_enabled(recipient_user):
        project_coordinator = course.project_coordinator
        to_addresses = [recipient_user.email]
        from_address = settings.PUBLISHER_FROM_EMAIL
        context = {
            'recipient_name': recipient_user.full_name or recipient_user.username if recipient_user else '',
            'sender_name': user.full_name or user.username,
            'course_name': course_name if course_name else course.title,
            'contact_us_email': project_coordinator.email if project_coordinator else '',
            'page_url': 'https://{host}{path}'.format(
                host=Site.objects.get_current().domain.strip('/'), path=page_path
            )
        }
        template = get_template(txt_template)
        plain_content = template.render(context)
        template = get_template(html_template)
        html_content = template.render(context)

        email_msg = EmailMultiAlternatives(
            subject, plain_content, from_address, to_addresses
        )
        email_msg.attach_alternative(html_content, 'text/html')
        email_msg.send()


def send_email_for_send_for_review_course_run(course_run, user):
    """ Send email when course-run is submitted for review.

        Arguments:
            course-run (Object): CourseRun object
            user (Object): User object
    """
    txt_template = 'publisher/email/course_run/send_for_review.txt'
    html_template = 'publisher/email/course_run/send_for_review.html'
    subject = _('Changes to {title} are ready for review').format(title=course_run.course.title)  # pylint: disable=no-member

    try:
        page_path = reverse('publisher:publisher_course_run_detail', kwargs={'pk': course_run.id})
        send_course_workflow_email(course_run.course, user, subject, txt_template, html_template, page_path)
    except Exception:  # pylint: disable=broad-except
        logger.exception('Failed to send email notifications send for review of course-run %s', course_run.id)


def send_email_for_mark_as_reviewed_course_run(course_run, user):
    """ Send email when course-run is marked as reviewed.

        Arguments:
            course-run (Object): CourseRun object
            user (Object): User object
    """
    txt_template = 'publisher/email/course_run/mark_as_reviewed.txt'
    html_template = 'publisher/email/course_run/mark_as_reviewed.html'

    run_name = '{pacing_type}: {start_date}'.format(
        pacing_type=course_run.get_pacing_type_display(),
        start_date=course_run.start.strftime("%B %d, %Y")
    )
    subject = _('Changes to {run_name} has been marked as reviewed').format(run_name=run_name)  # pylint: disable=no-member

    try:
        page_path = reverse('publisher:publisher_course_run_detail', kwargs={'pk': course_run.id})
        send_course_workflow_email(
            course_run.course,
            user,
            subject,
            txt_template,
            html_template,
            page_path,
            course_name=run_name
        )
    except Exception:  # pylint: disable=broad-except
        logger.exception('Failed to send email notifications for mark as reviewed of course-run %s', course_run.id)


def send_email_to_publisher(course_run, user):
    """ Send email to publisher when course-run is marked as reviewed.

        Arguments:
            course_run (Object): CourseRun object
            user (Object): User object
    """
    txt_template = 'publisher/email/course_run/mark_as_reviewed.txt'
    html_template = 'publisher/email/course_run/mark_as_reviewed.html'

    run_name = '{pacing_type}: {start_date}'.format(
        pacing_type=course_run.get_pacing_type_display(),
        start_date=course_run.start.strftime("%B %d, %Y")
    )
    subject = _('Changes to {run_name} has been marked as reviewed').format(run_name=run_name)  # pylint: disable=no-member
    recipient_user = course_run.course.publisher

    try:
        if is_email_notification_enabled(recipient_user):
            project_coordinator = course_run.course.project_coordinator
            to_addresses = [recipient_user.email]
            from_address = settings.PUBLISHER_FROM_EMAIL
            page_path = reverse('publisher:publisher_course_run_detail', kwargs={'pk': course_run.id})
            context = {
                'recipient_name': recipient_user.full_name or recipient_user.username if recipient_user else '',
                'sender_name': user.full_name or user.username,
                'course_name': run_name,
                'contact_us_email': project_coordinator.email if project_coordinator else '',
                'page_url': 'https://{host}{path}'.format(
                    host=Site.objects.get_current().domain.strip('/'), path=page_path
                )
            }
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
        logger.exception('Failed to send email notifications for mark as reviewed of course-run %s', course_run.id)


def send_email_preview_accepted(course_run):
    """ Send email for preview approved to publisher and project coordinator.

        Arguments:
            course_run (Object): CourseRun object
    """
    txt_template = 'publisher/email/course_run/preview_accepted.txt'
    html_template = 'publisher/email/course_run/preview_accepted.html'

    run_name = '{pacing_type}: {start_date}'.format(
        pacing_type=course_run.get_pacing_type_display(),
        start_date=course_run.start.strftime("%B %d, %Y")
    )
    subject = _('Preview for {run_name} has been approved').format(run_name=run_name)  # pylint: disable=no-member
    publisher_user = course_run.course.publisher

    try:
        if is_email_notification_enabled(publisher_user):
            project_coordinator = course_run.course.project_coordinator
            to_addresses = [publisher_user.email]
            if is_email_notification_enabled(project_coordinator):
                to_addresses.append(project_coordinator.email)
            from_address = settings.PUBLISHER_FROM_EMAIL
            page_path = reverse('publisher:publisher_course_run_detail', kwargs={'pk': course_run.id})
            context = {
                'course_name': run_name,
                'contact_us_email': project_coordinator.email if project_coordinator else '',
                'page_url': 'https://{host}{path}'.format(
                    host=Site.objects.get_current().domain.strip('/'), path=page_path
                )
            }
            template = get_template(txt_template)
            plain_content = template.render(context)
            template = get_template(html_template)
            html_content = template.render(context)

            email_msg = EmailMultiAlternatives(
                subject, plain_content, from_address, to=[from_address], bcc=to_addresses
            )
            email_msg.attach_alternative(html_content, 'text/html')
            email_msg.send()
    except Exception:  # pylint: disable=broad-except
        message = 'Failed to send email notifications for preview approved of course-run [{id}].'.format(
            id=course_run.id
        )
        logger.exception(message)
        raise Exception(message)


def send_email_preview_page_is_available(course_run):
    """ Send email for course preview available to course team.

        Arguments:
            course_run (Object): CourseRun object
    """
    txt_template = 'publisher/email/course_run/preview_available.txt'
    html_template = 'publisher/email/course_run/preview_available.html'

    run_name = '{pacing_type}: {start_date}'.format(
        pacing_type=course_run.get_pacing_type_display(),
        start_date=course_run.start.strftime("%B %d, %Y")
    )
    subject = _('Preview for {run_name} is available').format(run_name=run_name)  # pylint: disable=no-member
    course_team_user = course_run.course.course_team_admin

    try:
        if is_email_notification_enabled(course_team_user):
            to_addresses = [course_team_user.email]
            from_address = settings.PUBLISHER_FROM_EMAIL
            project_coordinator = course_run.course.project_coordinator
            page_path = reverse('publisher:publisher_course_run_detail', kwargs={'pk': course_run.id})
            context = {
                'course_name': run_name,
                'contact_us_email': project_coordinator.email if project_coordinator else '',
                'page_url': 'https://{host}{path}'.format(
                    host=Site.objects.get_current().domain.strip('/'), path=page_path
                )
            }
            template = get_template(txt_template)
            plain_content = template.render(context)
            template = get_template(html_template)
            html_content = template.render(context)

            email_msg = EmailMultiAlternatives(
                subject, plain_content, from_address, to=[from_address], bcc=to_addresses
            )
            email_msg.attach_alternative(html_content, 'text/html')
            email_msg.send()

    except Exception:  # pylint: disable=broad-except
        logger.exception('Failed to send email notifications for preview available of course-run %s', course_run.id)
