from django.core.mail import EmailMessage
from django.template.loader import get_template

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
