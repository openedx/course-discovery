""" Publisher Utils."""
from course_discovery.apps.core.models import User
from course_discovery.apps.publisher.constants import ADMIN_GROUP_NAME, INTERNAL_USER_GROUP_NAME


def is_email_notification_enabled(user):
    """ Check email notification is enabled for the user.

    Arguments:
        user (User): User object

    Returns:
        enable_email_notification | True
    """
    if hasattr(user, 'attributes'):
        return user.attributes.enable_email_notification

    return True


def is_publisher_admin(user):
    """ Returns True if the user is a Publisher administrator.

    Arguments:
        user (:obj:`User`): User whose permissions should be checked.

    Returns:
        bool: True, if user is an administrator; otherwise, False.
    """
    return user.groups.filter(name=ADMIN_GROUP_NAME).exists()


def is_internal_user(user):
    """ Returns True if the user is an internal user.

    Arguments:
        user (:obj:`User`): User whose permissions should be checked.

    Returns:
        bool: True, if user is an internal user; otherwise, False.
    """
    return user.groups.filter(name=INTERNAL_USER_GROUP_NAME).exists()


def get_internal_users():
    """
    Returns a list of all internal users

    Returns:
        list
    """
    return list(User.objects.filter(groups__name=INTERNAL_USER_GROUP_NAME))
