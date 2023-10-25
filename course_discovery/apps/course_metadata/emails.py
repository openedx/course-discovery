import datetime
import json
import logging
from email.mime.text import MIMEText
from urllib.parse import urljoin

import dateutil.parser
from django.conf import settings
from django.core.mail.message import EmailMultiAlternatives
from django.template.loader import get_template
from django.utils.translation import gettext as _
from opaque_keys.edx.keys import CourseKey

from course_discovery.apps.core.models import User
from course_discovery.apps.course_metadata.choices import CourseRunStatus
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


def get_project_coordinators(org):
    """ Get the registered project coordinators for an organization.

        Only returns the first one. Technically the database supports multiple. But in practice, we only use one.
        Requires a OrganizationUserRole to be set up first.

        Arguments:
            org (Object): Organization object

        Returns:
            list(Object): a list of User objects or None if no project coordinator is registered
    """
    # Model imports here to avoid a circular import
    from course_discovery.apps.publisher.models import OrganizationUserRole  # pylint: disable=import-outside-toplevel

    if not org:
        return None

    project_coordinators = [pc.user for pc in OrganizationUserRole.objects.filter(
        organization=org, role=InternalUserRole.ProjectCoordinator.value
    ).select_related('user')]
    return project_coordinators or None


def send_email(template_name, subject, to_users, recipient_name,
               course_run=None, course=None, context=None, project_coordinators=None):
    """ Send an email template out to the given users with some standard context variables.

        Arguments:
            template_name (str): path to template without filename extension
            subject (str): subject line for the email
            to_users (list(Object)): a list of User objects to send the email to, if they have notifications enabled
            recipient_name (str): a string to use to greet the user (use a team name if multiple users)
            course_run (Object): CourseRun object
            course (Object): Course object
            context (dict): additional context for the template
            project_coordinators (list): optional optimization if you have the PC User(s) already, to prevent a lookup
    """
    course = course or course_run.course
    partner = course.partner
    org = course.authoring_organizations.first()
    project_coordinators = project_coordinators or get_project_coordinators(org)
    if not project_coordinators:
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
        run_studio_url = urljoin(studio_url, f'course/{course_run.key}')
        review_url = urljoin(publisher_url, f'courses/{course.uuid}')
        base_context.update({
            'course_name': course_run.title,
            'course_key': course_run.key,
            'course_run_number': CourseKey.from_string(course_run.key).run,
            'recipient_name': recipient_name,
            'platform_name': settings.PLATFORM_NAME,
            'org_name': org.name,
            'contact_us_emails': [project_coordinator.email for project_coordinator in project_coordinators],
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
            'contact_us_emails': [project_coordinator.email for project_coordinator in project_coordinators],
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
    project_coordinators = get_project_coordinators(org)
    if not project_coordinators:
        log_missing_project_coordinator(course_run.course.key, org, template_name)
        return

    send_email(template_name, subject, project_coordinators, _('Project Coordinator team'), context=context,
               project_coordinators=project_coordinators, course_run=course_run)


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

    if course_run.course.is_external_course:
        logger.info("Skipping send email to the editors of external course: '%s' with type: '%s'",
                    course_run.course.title,
                    course_run.course.type.slug
                    )
        return

    editors = CourseEditor.course_editors(course_run.course)
    send_email(template_name, subject, editors, _('course team'), context=context, course_run=course_run)


def send_email_for_legal_review(course_run):
    """ Send email when a course run is submitted for legal review.

        Arguments:
            course_run (Object): CourseRun object
    """
    subject = _('Legal review requested: {title}').format(title=course_run.title)
    send_email_to_legal(course_run, 'course_metadata/email/legal_review', subject)


def send_email_to_notify_course_watchers(course, course_run_publish_date, course_run_status):
    """
    Send email to the watchers of the course when the course run is scheduled or published.

    Arguments:
        course (Object): Course object
        course_run_publish_date (datetime): Course run publish date
        course_run_status (str): Course run status
    """
    subject = _('Course URL for {title}').format(title=course.title)
    context = {
        'course_name': course.title,
        'marketing_service_name': settings.MARKETING_SERVICE_NAME,
        'course_publish_date': course_run_publish_date.strftime("%m/%d/%Y"),
        'is_course_published': course_run_status == CourseRunStatus.Published,
        'course_marketing_url': course.marketing_url,
        'course_preview_url': course.preview_url,
    }
    to_users = course.watchers
    txt_template = 'course_metadata/email/watchers_course_url.txt'
    html_template = 'course_metadata/email/watchers_course_url.html'
    template = get_template(txt_template)
    plain_content = template.render(context)
    template = get_template(html_template)
    html_content = template.render(context)

    email_msg = EmailMultiAlternatives(
        subject, plain_content, settings.PUBLISHER_FROM_EMAIL, to_users
    )
    email_msg.attach_alternative(html_content, 'text/html')

    try:
        email_msg.send()
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception(
            f'Failed to send email notification with subject "{subject}" to users {to_users}. Error: {exc}'
        )


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
    project_coordinators = get_project_coordinators(org)
    recipients = list(CourseEditor.course_editors(course))
    if project_coordinators:
        recipients.extend(project_coordinators)

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
                   course=course, context=context, project_coordinators=project_coordinators)
    except Exception:  # pylint: disable=broad-except
        logger.exception('Failed to send email notifications for comment on course %s', course.uuid)


def send_ingestion_email(partner, subject, to_users, product_type, product_source, ingestion_details):
    """ Send an overall report of a product's ingestion.

        Arguments:
            partner (Object): Partner model object
            subject (str): subject line for email
            to_users (list(str)): a list of email addresses to whom the email should be sent to
            product_type (str): the product whose ingestion has been run
            product_source (Object): the source of the product
            ingestion_details (dict): Stats of ingestion, along with reported errors
    """
    products_json = ingestion_details.pop('products_json', None)
    context = {
        **ingestion_details,
        'product_type': product_type,
        'publisher_url': partner.publisher_url,
        'ingestion_contact_email': settings.LOADER_INGESTION_CONTACT_EMAIL,
        'marketing_service_name': settings.MARKETING_SERVICE_NAME,
        'product_source': product_source.name,
    }
    txt_template = 'course_metadata/email/loader_ingestion.txt'
    html_template = 'course_metadata/email/loader_ingestion.html'
    template = get_template(txt_template)
    plain_content = template.render(context)
    template = get_template(html_template)
    html_content = template.render(context)

    email_msg = EmailMultiAlternatives(
        subject, plain_content, settings.PUBLISHER_FROM_EMAIL, to_users
    )
    email_msg.attach_alternative(html_content, 'text/html')
    if products_json:
        products_json = json.dumps(products_json, indent=2)
        email_msg.attach(filename='products.json', content=products_json, mimetype='application/json')

    try:
        email_msg.send()
    except Exception:  # pylint: disable=broad-except
        logger.exception(
            'Failure to send ingestion notification for product type %s, with subject "%s" and context "%s"',
            product_type,
            subject,
            context
        )


def send_email_for_slug_updates(stats, to_users, subject=None):
    """ Send an email with the summary of course slugs update.

        Arguments:
            stats (str): stats of course slugs update
            to_users (list(str)): a list of email addresses to whom the email should be sent to
            subject (str): subject line for email
    """
    subject = subject or 'Migrate Course Slugs Summary Report'
    body = 'Please find the attached csv file for the summary of course slugs update.'
    email_msg = EmailMultiAlternatives(
        subject, body, settings.PUBLISHER_FROM_EMAIL, to_users
    )
    attachment = MIMEText(stats, 'csv')
    attachment.add_header('Content-Disposition', 'attachment', filename='slugs_update_summary.csv')
    email_msg.attach(attachment)
    email_msg.send()
