""" Publisher context processors. """

from course_discovery.apps.publisher.utils import is_email_notification_enabled


def publisher(request):
    return {
        'is_email_notification_enabled': is_email_notification_enabled(request.user)
    }
