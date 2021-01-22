""" Publisher Utils."""
import re

VALID_CHARS_IN_COURSE_NUM_AND_ORG_KEY = re.compile(r'^[a-zA-Z0-9._-]*$')


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


def is_publisher_user(user):
    """ Returns True if the user is part of any group.

    Arguments:
        user (:obj:`User`): User whose permissions should be checked.

    Returns:
        bool: True, if user is an publisher user; otherwise, False.
    """
    return user.groups.exists()
