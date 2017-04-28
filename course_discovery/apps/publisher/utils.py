""" Publisher Utils."""
from dateutil import parser

from course_discovery.apps.core.models import User
from course_discovery.apps.publisher.constants import (ADMIN_GROUP_NAME, INTERNAL_USER_GROUP_NAME,
                                                       PROJECT_COORDINATOR_GROUP_NAME)


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
        list: internal users list
    """
    return list(User.objects.filter(groups__name=INTERNAL_USER_GROUP_NAME))


def is_project_coordinator_user(user):
    """ Returns True if the user is an project coordinator user.

    Arguments:
        user (:obj:`User`): User whose permissions should be checked.

    Returns:
        bool: True, if user is an PC user; otherwise, False.
    """
    return user.groups.filter(name=PROJECT_COORDINATOR_GROUP_NAME).exists()


def is_publisher_user(user):
    """ Returns True if the user is part of any group.

    Arguments:
        user (:obj:`User`): User whose permissions should be checked.

    Returns:
        bool: True, if user is an publisher user; otherwise, False.
    """
    return user.groups.exists()


def make_bread_crumbs(links):
    """ Returns lists of dicts containing bread-crumbs url and slug.

    Arguments:
        links (list): List of tuple contains links and slug.

    Returns:
        list: list containing dicts [{'url':'/courses/', 'slug':'test'}].
    """
    return [
        {
            "url": url,
            "slug": slug,
        }
        for url, slug in links
    ]


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


def parse_datetime_field(date):
    """
    Parse datetime field to make same format YYYY-MM-DD 00:00:00.

    Arguments:
        date (str): date string in any possible format

    Returns:
        datetime (object): returns datetime object after parsing
    """
    if not date:
        return

    try:
        return parser.parse(date)

    except ValueError:
        return
