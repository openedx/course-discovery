""" Publisher context processors. """

from course_discovery.apps.publisher.utils import is_email_notification_enabled, publisher_url


def publisher(request):
    return {
        'is_email_notification_enabled': is_email_notification_enabled(request.user),
        'publisher_url': publisher_url(request.user),
    }
