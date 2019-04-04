import logging
from django.conf import settings
from django.core.mail.message import EmailMultiAlternatives
from django.template.loader import get_template
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from opaque_keys.edx.keys import CourseKey

from course_discovery.apps.core.models import User
from course_discovery.apps.publisher.choices import PublisherUserRole
from course_discovery.apps.publisher.constants import LEGAL_TEAM_GROUP_NAME
from course_discovery.apps.publisher.utils import is_email_notification_enabled

logger = logging.getLogger(__name__)


def send_email_for_studio_instance_created(course_run, site):
    """ Send an email to course team on studio instance creation.

        Arguments:
            course_run (CourseRun): CourseRun object
            site (Site): Current site
    """
    try:
        course_key = CourseKey.from_string(course_run.lms_course_id)
        object_path = reverse('publisher:publisher_course_run_detail', kwargs={'pk': course_run.id})
        subject = _('Studio URL created: {title} {run_number}').format(  # pylint: disable=no-member
            title=course_run.course.title,
            run_number=course_key.run
        )

        to_addresses = [course_run.course.course_team_admin.email]
        from_address = settings.PUBLISHER_FROM_EMAIL

        course_team_admin = course_run.course.course_team_admin
        project_coordinator = course_run.course.project_coordinator

        context = {
            'course_run': course_run,
            'course_run_page_url': 'https://{host}{path}'.format(
                host=site.domain.strip('/'), path=object_path
            ),
            'course_name': course_run.course.title,
            'from_address': from_address,
            'course_team_name': course_team_admin.get_full_name() or course_team_admin.username,
            'project_coordinator_name': project_coordinator.get_full_name() or project_coordinator.username,
            'contact_us_email': project_coordinator.email,
            'studio_url': course_run.studio_url
        }

        txt_template_path = 'publisher/email/studio_instance_created.txt'
        html_template_path = 'publisher/email/studio_instance_created.html'

        txt_template = get_template(txt_template_path)
        plain_content = txt_template.render(context)
        html_template = get_template(html_template_path)
        html_content = html_template.render(context)
        email_msg = EmailMultiAlternatives(subject, plain_content, from_address, to=to_addresses)
        email_msg.attach_alternative(html_content, 'text/html')
        email_msg.send()
    except Exception:  # pylint: disable=broad-except
        error_message = 'Failed to send email notifications for course_run [{run_id}]'.format(run_id=course_run.id)
        logger.exception(error_message)
        raise Exception(error_message)


def send_email_for_course_creation(course, course_run, site):
    """ Send the emails for a course creation.

        Arguments:
            course (Course): Course object
            course_run (CourseRun): CourseRun object
            site (Site): Current site
    """
    txt_template = 'publisher/email/course_created.txt'
    html_template = 'publisher/email/course_created.html'

    subject = _('Studio URL requested: {title}').format(title=course.title)  # pylint: disable=no-member
    project_coordinator = course.project_coordinator
    course_team = course.course_team_admin

    if is_email_notification_enabled(project_coordinator):
        try:
            to_addresses = [project_coordinator.email]
            from_address = settings.PUBLISHER_FROM_EMAIL

            context = {
                'course_title': course.title,
                'date': course_run.created.strftime("%B %d, %Y"),
                'time': course_run.created.strftime("%H:%M:%S"),
                'course_team_name': course_team.get_full_name(),
                'project_coordinator_name': project_coordinator.get_full_name(),
                'dashboard_url': 'https://{host}{path}'.format(
                    host=site.domain.strip('/'), path=reverse('publisher:publisher_dashboard')
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


def send_email_for_send_for_review(course, user, site):
    """ Send email when course is submitted for review.

        Arguments:
            course (Object): Course object
            user (Object): User object
            site (Site): Current site
    """
    txt_template = 'publisher/email/course/send_for_review.txt'
    html_template = 'publisher/email/course/send_for_review.html'
    subject = _('Review requested: {title}').format(title=course.title)  # pylint: disable=no-member

    try:
        recipient_user = course.marketing_reviewer
        user_role = course.course_user_roles.get(user=user)
        if user_role.role == PublisherUserRole.MarketingReviewer:
            recipient_user = course.course_team_admin

        page_path = reverse('publisher:publisher_course_detail', kwargs={'pk': course.id})
        context = {
            'course_name': course.title,
            'sender_team': 'course team' if user_role.role == PublisherUserRole.CourseTeam else 'marketing team',
            'page_url': 'https://{host}{path}'.format(
                host=site.domain.strip('/'), path=page_path
            )
        }

        send_course_workflow_email(course, user, subject, txt_template, html_template, context, recipient_user, site)
    except Exception:  # pylint: disable=broad-except
        logger.exception('Failed to send email notifications send for review of course %s', course.id)


def send_email_for_mark_as_reviewed(course, user, site):
    """ Send email when course is marked as reviewed.

        Arguments:
            course (Object): Course object
            user (Object): User object
            site (Site): Current site
    """
    txt_template = 'publisher/email/course/mark_as_reviewed.txt'
    html_template = 'publisher/email/course/mark_as_reviewed.html'
    subject = _('Review complete: {title}').format(title=course.title)  # pylint: disable=no-member

    try:
        recipient_user = course.marketing_reviewer
        user_role = course.course_user_roles.get(user=user)
        if user_role.role == PublisherUserRole.MarketingReviewer:
            recipient_user = course.course_team_admin

        page_path = reverse('publisher:publisher_course_detail', kwargs={'pk': course.id})
        context = {
            'course_name': course.title,
            'sender_team': 'course team' if user_role.role == PublisherUserRole.CourseTeam else 'marketing team',
            'page_url': 'https://{host}{path}'.format(
                host=site.domain.strip('/'), path=page_path
            )
        }

        send_course_workflow_email(course, user, subject, txt_template, html_template, context, recipient_user, site)
    except Exception:  # pylint: disable=broad-except
        logger.exception('Failed to send email notifications mark as reviewed of course %s', course.id)


def send_course_workflow_email(course, user, subject, txt_template, html_template, context, recipient_user, site):
    """ Send email for course workflow state change.

        Arguments:
            course (Object): Course object
            user (Object): User object
            subject (String): Email subject
            txt_template: (String): Email text template path
            html_template: (String): Email html template path
            context: (Dict): Email template context
            recipient_user: (Object): User object
            site (Site): Current site
    """

    if is_email_notification_enabled(recipient_user):
        project_coordinator = course.project_coordinator
        to_addresses = [recipient_user.email]
        from_address = settings.PUBLISHER_FROM_EMAIL

        course_page_path = reverse('publisher:publisher_course_detail', kwargs={'pk': course.id})

        context.update(
            {
                'recipient_name': recipient_user.full_name or recipient_user.username if recipient_user else '',
                'sender_name': user.full_name or user.username,
                'org_name': course.organizations.all().first().name,
                'contact_us_email': project_coordinator.email if project_coordinator else '',
                'course_page_url': 'https://{host}{path}'.format(
                    host=site.domain.strip('/'), path=course_page_path
                )
            }
        )

        template = get_template(txt_template)
        plain_content = template.render(context)
        template = get_template(html_template)
        html_content = template.render(context)

        email_msg = EmailMultiAlternatives(
            subject, plain_content, from_address, to_addresses
        )
        email_msg.attach_alternative(html_content, 'text/html')
        email_msg.send()


def send_email_for_send_for_review_course_run(course_run, user, site):
    """ Send email when course-run is submitted for review.

        Arguments:
            course-run (Object): CourseRun object
            user (Object): User object
            site (Site): Current site
    """
    course = course_run.course
    course_key = CourseKey.from_string(course_run.lms_course_id)
    txt_template = 'publisher/email/course_run/send_for_review.txt'
    html_template = 'publisher/email/course_run/send_for_review.html'
    subject = _('Review requested: {title} {run_number}').format(  # pylint: disable=no-member
        title=course.title,
        run_number=course_key.run)

    try:
        recipient_user = course.project_coordinator
        user_role = course.course_user_roles.get(user=user)
        if user_role.role == PublisherUserRole.ProjectCoordinator:
            recipient_user = course.course_team_admin

        page_path = reverse('publisher:publisher_course_run_detail', kwargs={'pk': course_run.id})
        context = {
            'course_name': course.title,
            'run_number': course_key.run,
            'sender_team': 'course team' if user_role.role == PublisherUserRole.CourseTeam else 'project coordinators',
            'page_url': 'https://{host}{path}'.format(
                host=site.domain.strip('/'), path=page_path
            ),
            'studio_url': course_run.studio_url
        }

        send_course_workflow_email(course, user, subject, txt_template, html_template, context, recipient_user, site)
    except Exception:  # pylint: disable=broad-except
        logger.exception('Failed to send email notifications send for review of course-run %s', course_run.id)


def send_email_for_mark_as_reviewed_course_run(course_run, user, site):
    """ Send email when course-run is marked as reviewed.

        Arguments:
            course_run (Object): CourseRun object
            user (Object): User object
            site (Site): Current site
    """
    txt_template = 'publisher/email/course_run/mark_as_reviewed_pc.txt'
    html_template = 'publisher/email/course_run/mark_as_reviewed_pc.html'
    course = course_run.course
    course_key = CourseKey.from_string(course_run.lms_course_id)
    subject = _('Review complete: {course_name} {run_number}').format(  # pylint: disable=no-member
        course_name=course.title,
        run_number=course_key.run
    )

    try:
        user_role = course.course_user_roles.get(user=user)
        # Send this email only to PC if approving person is course team member
        if user_role.role == PublisherUserRole.CourseTeam:
            page_path = reverse('publisher:publisher_course_run_detail', kwargs={'pk': course_run.id})
            recipient_user = course.project_coordinator

            context = {
                'course_name': course.title,
                'run_number': course_key.run,
                'sender_team': 'course team',
                'page_url': 'https://{host}{path}'.format(
                    host=site.domain.strip('/'), path=page_path
                )
            }

            send_course_workflow_email(
                course, user, subject, txt_template, html_template, context, recipient_user, site
            )
    except Exception:  # pylint: disable=broad-except
        logger.exception('Failed to send email notifications for mark as reviewed of course-run %s', course_run.id)


def send_email_to_publisher(course_run, user, site):
    """ Send email to publisher when course-run is marked as reviewed.

        Arguments:
            course_run (Object): CourseRun object
            user (Object): User object
            site (Site): Current site
    """
    txt_template = 'publisher/email/course_run/mark_as_reviewed.txt'
    html_template = 'publisher/email/course_run/mark_as_reviewed.html'

    course_key = CourseKey.from_string(course_run.lms_course_id)
    subject = _('Review complete: {course_name} {run_number}').format(  # pylint: disable=no-member
        course_name=course_run.course.title,
        run_number=course_key.run
    )

    recipient_user = course_run.course.publisher
    user_role = course_run.course.course_user_roles.get(user=user)
    sender_team = 'course team'
    if user_role.role == PublisherUserRole.MarketingReviewer:
        sender_team = 'marketing team'

    try:
        if is_email_notification_enabled(recipient_user):
            project_coordinator = course_run.course.project_coordinator
            to_addresses = [recipient_user.email]
            from_address = settings.PUBLISHER_FROM_EMAIL
            page_path = reverse('publisher:publisher_course_run_detail', kwargs={'pk': course_run.id})
            context = {
                'recipient_name': recipient_user.full_name or recipient_user.username if recipient_user else '',
                'sender_name': user.full_name or user.username,
                'course_name': course_run.course.title,
                'run_number': course_key.run,
                'org_name': course_run.course.organizations.all().first().name,
                'sender_team': sender_team,
                'contact_us_email': project_coordinator.email if project_coordinator else '',
                'page_url': 'https://{host}{path}'.format(
                    host=site.domain.strip('/'), path=page_path
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


def send_email_preview_accepted(course_run, site):
    """ Send email for preview approved to publisher and project coordinator.

        Arguments:
            course_run (Object): CourseRun object
            site (Site): Current site
    """
    txt_template = 'publisher/email/course_run/preview_accepted.txt'
    html_template = 'publisher/email/course_run/preview_accepted.html'

    course = course_run.course
    publisher_user = course.publisher

    try:
        if is_email_notification_enabled(publisher_user):
            course_key = CourseKey.from_string(course_run.lms_course_id)
            subject = _('Publication requested: {course_name} {run_number}').format(  # pylint: disable=no-member
                course_name=course.title,
                run_number=course_key.run)
            project_coordinator = course.project_coordinator
            to_addresses = [publisher_user.email]
            if is_email_notification_enabled(project_coordinator):
                to_addresses.append(project_coordinator.email)
            from_address = settings.PUBLISHER_FROM_EMAIL
            page_path = reverse('publisher:publisher_course_run_detail', kwargs={'pk': course_run.id})
            course_page_path = reverse('publisher:publisher_course_detail', kwargs={'pk': course_run.course.id})
            context = {
                'course_name': course.title,
                'run_number': course_key.run,
                'publisher_role_name': PublisherUserRole.Publisher,
                'course_team': course.course_team_admin,
                'org_name': course.organizations.all().first().name,
                'contact_us_email': project_coordinator.email if project_coordinator else '',
                'page_url': 'https://{host}{path}'.format(
                    host=site.domain.strip('/'), path=page_path
                ),
                'course_page_url': 'https://{host}{path}'.format(
                    host=site.domain.strip('/'), path=course_page_path
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


def send_email_preview_page_is_available(course_run, site):
    """ Send email for course preview available to course team.

        Arguments:
            course_run (Object): CourseRun object
            site (Site): Current site
    """
    txt_template = 'publisher/email/course_run/preview_available.txt'
    html_template = 'publisher/email/course_run/preview_available.html'
    course_team_user = course_run.course.course_team_admin

    try:
        if is_email_notification_enabled(course_team_user):
            course_key = CourseKey.from_string(course_run.lms_course_id)
            subject = _('Review requested: Preview for {course_name} {run_number}').format(  # pylint: disable=no-member
                course_name=course_run.course.title,
                run_number=course_key.run
            )
            to_addresses = [course_team_user.email]
            from_address = settings.PUBLISHER_FROM_EMAIL
            project_coordinator = course_run.course.project_coordinator
            context = {
                'sender_role': PublisherUserRole.Publisher,
                'recipient_name': course_team_user.get_full_name() or course_team_user.username,
                'course_run': course_run,
                'course_run_key': course_key,
                'course_run_publisher_url': 'https://{host}{path}'.format(
                    host=site.domain.strip('/'), path=course_run.get_absolute_url()),
                'contact_us_email': project_coordinator.email if project_coordinator else '',
                'platform_name': settings.PLATFORM_NAME
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
        error_message = 'Failed to send email notifications for preview available of course-run {run_id}'.format(
            run_id=course_run.id
        )
        logger.exception(error_message)
        raise Exception(error_message)


def send_course_run_published_email(course_run, site):
    """ Send email when course run is published by publisher.

        Arguments:
            course_run (Object): CourseRun object
            site (Site): Current site
    """
    txt_template = 'publisher/email/course_run/published.txt'
    html_template = 'publisher/email/course_run/published.html'
    course_team_user = course_run.course.course_team_admin

    try:
        if is_email_notification_enabled(course_team_user):
            course_key = CourseKey.from_string(course_run.lms_course_id)
            subject = _('Publication complete: About page for {course_name} {run_number}').format(  # pylint:disable=no-member
                course_name=course_run.course.title,
                run_number=course_key.run
            )
            from_address = settings.PUBLISHER_FROM_EMAIL
            project_coordinator = course_run.course.project_coordinator
            page_path = reverse('publisher:publisher_course_run_detail', kwargs={'pk': course_run.id})
            course_page_path = reverse('publisher:publisher_course_detail', kwargs={'pk': course_run.course.id})
            context = {
                'sender_role': PublisherUserRole.Publisher,
                'course_name': course_run.course.title,
                'preview_url': course_run.preview_url,
                'course_run_number': course_key.run,
                'recipient_name': course_team_user.get_full_name() or course_team_user.username,
                'contact_us_email': project_coordinator.email if project_coordinator else '',
                'page_url': 'https://{host}{path}'.format(
                    host=site.domain.strip('/'), path=page_path
                ),
                'course_page_url': 'https://{host}{path}'.format(
                    host=site.domain.strip('/'), path=course_page_path
                ),
                'platform_name': settings.PLATFORM_NAME,
            }
            template = get_template(txt_template)
            plain_content = template.render(context)
            template = get_template(html_template)
            html_content = template.render(context)

            email_kwargs = {
                'cc': [project_coordinator.email] if project_coordinator else [],
            }
            email_msg = EmailMultiAlternatives(subject, plain_content, from_address, to=[course_team_user.email],
                                               **email_kwargs)
            email_msg.attach_alternative(html_content, 'text/html')
            email_msg.send()

    except Exception:  # pylint: disable=broad-except
        error_message = 'Failed to send email notifications for course published of course-run [{run_id}]'.format(
            run_id=course_run.id
        )
        logger.exception(error_message)
        raise Exception(error_message)


def send_change_role_assignment_email(course_role, former_user, site):
    """ Send email for role assignment changed.

        Arguments:
            course_role (Object): CourseUserRole object
            former_user (Object): User object
            site (Site): Current site
    """
    txt_template = 'publisher/email/role_assignment_changed.txt'
    html_template = 'publisher/email/role_assignment_changed.html'
    course = course_role.course
    project_coordinator = course.project_coordinator
    course_team_admin = course.course_team_admin
    from_address = settings.PUBLISHER_FROM_EMAIL

    try:
        role_name = course_role.get_role_display()
        subject = _('{role_name} changed for {course_title}').format(  # pylint: disable=no-member
            role_name=role_name.lower(),
            course_title=course.title
        )

        to_addresses = course.get_course_users_emails()
        if former_user.email not in to_addresses:
            to_addresses.append(former_user.email)

        if course_team_admin and course_team_admin.email in to_addresses:
            to_addresses.remove(course_team_admin.email)

        page_path = reverse('publisher:publisher_course_detail', kwargs={'pk': course.id})
        course_url = 'https://{host}{path}'.format(host=site.domain.strip('/'), path=page_path)
        context = {
            'course_title': course.title,
            'role_name': role_name.lower(),
            'former_user_name': former_user.get_full_name() or former_user.username,
            'current_user_name': course_role.user.get_full_name() or course_role.user.username,
            'contact_us_email': getattr(project_coordinator, 'email', ''),
            'course_url': course_url,
            'platform_name': settings.PLATFORM_NAME,
        }
        template = get_template(txt_template)
        plain_content = template.render(context)
        template = get_template(html_template)
        html_content = template.render(context)

        email_msg = EmailMultiAlternatives(subject, plain_content, from_address, to=to_addresses)
        email_msg.attach_alternative(html_content, 'text/html')
        email_msg.send()

    except Exception:  # pylint: disable=broad-except
        error_message = 'Failed to send email notifications for change role assignment of role: [{role_id}]'.format(
            role_id=course_role.id
        )
        logger.exception(error_message)
        raise Exception(error_message)


def send_email_for_seo_review(course, site):
    """ Send email when course is submitted for seo review.

        Arguments:
            course (Object): Course object
            site (Site): Current site
    """
    txt_template = 'publisher/email/course/seo_review.txt'
    html_template = 'publisher/email/course/seo_review.html'
    subject = _('Legal review requested: {title}').format(title=course.title)  # pylint: disable=no-member

    try:
        legal_team_users = User.objects.filter(groups__name=LEGAL_TEAM_GROUP_NAME)
        project_coordinator = course.project_coordinator
        to_addresses = [user.email for user in legal_team_users]  # pylint: disable=not-an-iterable
        from_address = settings.PUBLISHER_FROM_EMAIL

        course_page_path = reverse('publisher:publisher_course_detail', kwargs={'pk': course.id})

        context = {
            'course_name': course.title,
            'sender_team': _('Course team'),
            'recipient_name': _('Legal Team'),
            'org_name': course.organizations.all().first().name,
            'contact_us_email': project_coordinator.email,
            'course_page_url': 'https://{host}{path}'.format(
                host=site.domain.strip('/'), path=course_page_path
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
        logger.exception('Failed to send email notifications for legal review requested of course %s', course.id)


def send_email_for_published_course_run_editing(course_run, site):
    """ Send email when published course-run is edited.

        Arguments:
            course-run (Object): Course Run object
            site (Site): Current site
    """
    try:
        course = course_run.course
        publisher_user = course.publisher
        course_team_user = course_run.course.course_team_admin
        course_key = CourseKey.from_string(course_run.lms_course_id)

        txt_template = 'publisher/email/course_run/published_course_run_editing.txt'
        html_template = 'publisher/email/course_run/published_course_run_editing.html'
        subject = _('Changes to published course run: {title} {run_number}').format(  # pylint: disable=no-member
            title=course.title,
            run_number=course_key.run
        )

        to_addresses = [publisher_user.email]
        from_address = settings.PUBLISHER_FROM_EMAIL
        object_path = reverse('publisher:publisher_course_run_detail', kwargs={'pk': course_run.id})

        context = {
            'course_name': course.title,
            'course_team': course_team_user.get_full_name() or course_team_user.username,
            'recipient_name': publisher_user.get_full_name() or publisher_user.username,
            'contact_us_email': course.project_coordinator.email,
            'course_run_page_url': 'https://{host}{path}'.format(
                host=site.domain.strip('/'), path=object_path
            ),
            'course_run_number': course_key.run,
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
        logger.exception('Failed to send email notifications for publisher course-run [%s] editing.', course_run.id)
