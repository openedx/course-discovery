import datetime
import logging
from urllib.parse import urljoin

import dateutil.parser
from django.conf import settings
from django.core.mail.message import EmailMultiAlternatives
from django.template.loader import get_template
from django.utils.translation import ugettext as _
from opaque_keys.edx.keys import CourseKey

from course_discovery.apps.core.models import User
from course_discovery.apps.publisher.choices import InternalUserRole
from course_discovery.apps.publisher.constants import LEGAL_TEAM_GROUP_NAME
from course_discovery.apps.publisher.utils import is_email_notification_enabled

logger = logging.getLogger(__name__)


def log_missing_project_coordinator(key, org, template_name):
    """ Print a log message about an unregistered project coordinator.

        This is separated out to avoid duplicating strings in multiple places. Checks for why we might be missing the
        PC and then logs the correct error message.

        Arguments:
            key (str): The course key for this email
            org (Object): the relevant Organization object for the course run's course
            template_name (str): name of the email template this was for, used in the log message
    """
    if not org:
        logger.info(
            _('Not sending notification email for template {template} because no organization is defined '
              'for course {course}').format(template=template_name, course=key)
        )
    else:
        logger.info(
            _('Not sending notification email for template {template} because no project coordinator is defined '
              'for organization {org}').format(template=template_name, org=org.key)
        )


def get_project_coordinator(org):
    """ Get the registered project coordinator for an organization.

        Only returns the first one. Technically the database supports multiple. But in practice, we only use one.
        Requires a OrganizationUserRole to be set up first.

        Arguments:
            org (Object): Organization object

        Returns:
            Object: a User object or None if no project coordinator is registered
    """
    # Model imports here to avoid a circular import
    from course_discovery.apps.publisher.models import OrganizationUserRole  # pylint: disable=import-outside-toplevel

    if not org:
        return None

    role = OrganizationUserRole.objects.filter(organization=org,
                                               role=InternalUserRole.ProjectCoordinator).first()
    return role.user if role else None


def send_email(template_name, subject, to_users, recipient_name,
               course_run=None, course=None, context=None, project_coordinator=None):
    """ Send an email template out to the given users with some standard context variables.

        Arguments:
            template_name (str): path to template without filename extension
            subject (str): subject line for the email
            to_users (list(Object)): a list of User objects to send the email to, if they have notifications enabled
            recipient_name (str): a string to use to greet the user (use a team name if multiple users)
            course_run (Object): CourseRun object
            course (Object): Course object
            context (dict): additional context for the template
            project_coordinator (Object): optional optimization if you have the PC User already, to prevent a lookup
    """
    course = course or course_run.course
    partner = course.partner
    org = course.authoring_organizations.first()
    project_coordinator = project_coordinator or get_project_coordinator(org)
    if not project_coordinator:
        log_missing_project_coordinator(course.key, org, template_name)
        return

    publisher_url = partner.publisher_url
    if not publisher_url:
        logger.info(
            _('Not sending notification email for template {template} because no publisher URL is defined '
              'for partner {partner}').format(template=template_name, partner=partner.short_code)
        )
        return

    studio_url = partner.studio_url
    if not studio_url:
        logger.info(
            _('Not sending notification email for template {template} because no studio URL is defined '
              'for partner {partner}').format(template=template_name, partner=partner.short_code)
        )
        return

    base_context = {}
    if course_run:
        run_studio_url = urljoin(studio_url, 'course/{}'.format(course_run.key))
        review_url = urljoin(publisher_url, 'courses/{}'.format(course.uuid))
        base_context.update({
            'course_name': course_run.title,
            'course_key': course_run.key,
            'course_run_number': CourseKey.from_string(course_run.key).run,
            'recipient_name': recipient_name,
            'platform_name': settings.PLATFORM_NAME,
            'org_name': org.name,
            'contact_us_email': project_coordinator.email,
            'course_page_url': review_url,
            'studio_url': run_studio_url,
            'preview_url': course_run.marketing_url,
        })
    elif course:
        base_context.update({
            'course_name': course.title,
            'course_key': course.key,
            'recipient_name': recipient_name,
            'platform_name': settings.PLATFORM_NAME,
            'org_name': org.name,
            'contact_us_email': project_coordinator.email,
        })
    if context:
        base_context.update(context)

    txt_template = template_name + '.txt'
    html_template = template_name + '.html'
    template = get_template(txt_template)
    plain_content = template.render(base_context)
    template = get_template(html_template)
    html_content = template.render(base_context)

    to_addresses = [u.email for u in to_users if is_email_notification_enabled(u)]
    if not to_addresses:
        return

    email_msg = EmailMultiAlternatives(
        subject, plain_content, settings.PUBLISHER_FROM_EMAIL, to_addresses
    )
    email_msg.attach_alternative(html_content, 'text/html')

    try:
        email_msg.send()
    except Exception:  # pylint: disable=broad-except
        logger.exception('Failed to send email notification for template %s, with subject "%s"',
                         template_name, subject)


def send_email_to_legal(course_run, template_name, subject, context=None):
    """ Send a specific email template to all legal team members for a course run.

        Arguments:
            course_run (Object): CourseRun object
            template_name (str): path to template without filename extension
            subject (str): subject line for the email
            context (dict): additional context for the template
    """
    to_users = User.objects.filter(groups__name=LEGAL_TEAM_GROUP_NAME)
    send_email(template_name, subject, to_users, _('legal team'), context=context, course_run=course_run)


def send_email_to_project_coordinator(course_run, template_name, subject, context=None):
    """ Send a specific email template to the project coordinator for a course run.

        Arguments:
            course_run (Object): CourseRun object
            template_name (str): path to template without filename extension
            subject (str): subject line for the email
            context (dict): additional context for the template
    """
    org = course_run.course.authoring_organizations.first()
    project_coordinator = get_project_coordinator(org)
    if not project_coordinator:
        log_missing_project_coordinator(course_run.course.key, org, template_name)
        return

    recipient_name = project_coordinator.full_name or project_coordinator.username
    send_email(template_name, subject, [project_coordinator], recipient_name, context=context,
               project_coordinator=project_coordinator, course_run=course_run)


def send_email_to_editors(course_run, template_name, subject, context=None):
    """ Send a specific email template to all editors for a course run.

        Arguments:
            course_run (Object): CourseRun object
            template_name (str): path to template without filename extension
            subject (str): subject line for the email
            context (dict): additional context for the template
    """
    # Model imports here to avoid a circular import
    from course_discovery.apps.course_metadata.models import CourseEditor  # pylint: disable=import-outside-toplevel

    editors = CourseEditor.course_editors(course_run.course)
    send_email(template_name, subject, editors, _('course team'), context=context, course_run=course_run)


def send_email_for_legal_review(course_run):
    """ Send email when a course run is submitted for legal review.

        Arguments:
            course_run (Object): CourseRun object
    """
    subject = _('Legal review requested: {title}').format(title=course_run.title)
    send_email_to_legal(course_run, 'course_metadata/email/legal_review', subject)


def send_email_for_internal_review(course_run):
    """ Send email when a course run is submitted for internal review.

        Arguments:
            course_run (Object): CourseRun object
    """
    lms_admin_url = course_run.course.partner.lms_admin_url
    restricted_url = lms_admin_url and (lms_admin_url.rstrip('/') + '/embargo/restrictedcourse/')

    subject = _('Review requested: {key} - {title}').format(title=course_run.title, key=course_run.key)
    send_email_to_project_coordinator(course_run, 'course_metadata/email/internal_review', subject, context={
        'restricted_admin_url': restricted_url,
    })


def send_email_for_reviewed(course_run):
    """ Send email when a course run is successfully reviewed.

        Arguments:
            course_run (Object): CourseRun object
    """
    subject = _('Review complete: {title}').format(title=course_run.title)
    go_live = course_run.go_live_date
    if go_live and go_live < datetime.datetime.now(datetime.timezone.utc):
        go_live = None
    send_email_to_editors(course_run, 'course_metadata/email/reviewed', subject, context={
        'go_live_date': go_live and go_live.strftime('%x'),
    })


def send_email_for_go_live(course_run):
    """ Send email when a course run has successfully gone live and is now publicly available.

        Arguments:
            course_run (Object): CourseRun object
    """
    # We internally use the phrase "go live", but to users, we say "published"
    subject = _('Published: {title}').format(title=course_run.title)
    send_email_to_editors(course_run, 'course_metadata/email/go_live', subject)

    # PCs like to see the key too
    subject = _('Published: {key} - {title}').format(title=course_run.title, key=course_run.key)
    send_email_to_project_coordinator(course_run, 'course_metadata/email/go_live', subject)


def send_email_for_comment(comment, course, author):
    """ Send the emails for a comment.

        Arguments:
            comment (Dict): Comment dict returned from salesforce.py
            course (Course): Course object for the comment
            author (User): User object who made the post request
    """
    # Model imports here to avoid a circular import
    from course_discovery.apps.course_metadata.models import CourseEditor  # pylint: disable=import-outside-toplevel

    subject = _('Comment added: {title}').format(
        title=course.title
    )

    org = course.authoring_organizations.first()
    project_coordinator = get_project_coordinator(org)
    recipients = list(CourseEditor.course_editors(course))
    if project_coordinator:
        recipients.append(project_coordinator)

    # remove email of comment owner if exists
    recipients = filter(lambda x: x.email != author.email, recipients)

    context = {
        'comment_message': comment.get('comment'),
        'user_name': author.username,
        'course_name': course.title,
        'comment_date': dateutil.parser.parse(comment.get('created')),
        'page_url': '{url}/courses/{path}'.format(
            url=course.partner.publisher_url.strip('/'), path=course.uuid
        )
    }

    try:
        send_email('course_metadata/email/comment', subject, recipients, '',
                   course=course, context=context, project_coordinator=project_coordinator)
    except Exception:  # pylint: disable=broad-except
        logger.exception('Failed to send email notifications for comment on course %s', course.uuid)
