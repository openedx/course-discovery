""" Publisher context processors. """

from course_discovery.apps.publisher.utils import is_email_notification_enabled, is_on_old_publisher, publisher_url


def publisher(request):
    return {
        'is_email_notification_enabled': is_email_notification_enabled(request.user),
        'is_on_old_publisher': is_on_old_publisher(request.user),
        'publisher_url': publisher_url(request.user),
    }
