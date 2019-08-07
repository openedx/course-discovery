""" Publisher context processors. """

from course_discovery.apps.publisher.utils import is_email_notification_enabled, is_on_new_pub_fe, publisher_url


def publisher(request):
    return {
        'is_email_notification_enabled': is_email_notification_enabled(request.user),
        'is_on_new_pub_fe': is_on_new_pub_fe(request.user),
        'publisher_url': publisher_url(request.user),
    }
