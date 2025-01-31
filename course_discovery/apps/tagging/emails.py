import logging

from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import get_template
from django.urls import reverse

logger = logging.getLogger(__name__)


def send_email_for_course_verticals_update(report, to_users):
    """
    Send an overall report of an update_course_verticals mgmt command run
    """
    success_count = len(report['successes'])
    failure_count = len(report['failures'])
    context = {
        'total_count': success_count + failure_count,
        'failure_count': failure_count,
        'success_count': success_count,
        'failures': report['failures']
    }
    html_template = 'email/update_course_verticals.html'
    template = get_template(html_template)
    html_content = template.render(context)

    email = EmailMessage(
        "Update Course Verticals Command Summary",
        html_content,
        settings.PUBLISHER_FROM_EMAIL,
        to_users,
    )
    email.content_subtype = "html"
    email.send()


def send_email_for_course_vertical_assignment(course, to_users):
    """
    Sends an email to specified users requesting action to assign vertical and sub-vertical
    for a given course.
    """
    course_tagging_url = (
        f"{settings.DISCOVERY_BASE_URL}{reverse('tagging:course_tagging_detail', kwargs={'uuid': course.uuid})}"
    )

    context = {"course_name": course.title, "course_tagging_url": course_tagging_url}
    template = get_template("email/vertical_assigment.html")
    html_content = template.render(context)

    email = EmailMessage(
        f"Action Required: Assign Vertical and Sub-vertical for Course '{course.title}'",
        html_content,
        settings.PUBLISHER_FROM_EMAIL,
        to_users,
    )
    email.content_subtype = "html"

    try:
        email.send()
    except Exception as e:  # pylint: disable=broad-except
        logger.exception(
            f"Failed to send vertical assignment email for course '{course.title}' (UUID: {course.uuid}) to "
            f"recipients {', '.join(to_users)}. Error: {str(e)}"
        )
