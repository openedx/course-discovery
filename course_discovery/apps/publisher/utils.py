""" Publisher Utils."""
import re

from course_discovery.apps.publisher.constants import ADMIN_GROUP_NAME, INTERNAL_USER_GROUP_NAME

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


def is_publisher_user(user):
    """ Returns True if the user is part of any group.

    Arguments:
        user (:obj:`User`): User whose permissions should be checked.

    Returns:
        bool: True, if user is an publisher user; otherwise, False.
    """
    return user.groups.exists()


def has_role_for_course(course, user):
    """
    Check user has a role for course.

    Arguments:
        course: Course object
        user: User object

    Returns:
        bool: True, if user has a role for course; otherwise, False.
    """
    return course.course_user_roles.filter(user=user).exists()
