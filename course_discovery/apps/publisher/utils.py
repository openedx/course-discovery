""" Publisher Utils."""
import re

from dateutil import parser
from django.apps import apps

from course_discovery.apps.core.models import User
from course_discovery.apps.publisher.constants import (
    ADMIN_GROUP_NAME, INTERNAL_USER_GROUP_NAME, PROJECT_COORDINATOR_GROUP_NAME
)

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
        return None

    try:
        return parser.parse(date)

    except ValueError:
        return None


def find_discovery_course(publisher_course_run):
    """ Returns the discovery course where this publisher run already lives or should live. """
    # Ideal situation is that it already exists
    if publisher_course_run.discovery_counterpart:
        return publisher_course_run.discovery_counterpart.course

    # OK, it hasn't been pushed to the course metadata tables yet. Let's find where it will live.
    # We are intentionally not calling course.discovery_counterpart, because that simply looks at the
    # course key, and we want to be a little bit smarter than that if possible - sometimes course
    # runs get manually moved around.
    publisher_course = publisher_course_run.course
    for run in publisher_course.course_runs:  # returns newest first
        if run.discovery_counterpart:
            return run.discovery_counterpart.course

    return None


def user_orgs(user):
    # We load the organization model like this due to a circular import with the course
    # metadata models file
    Organization = apps.get_model('course_metadata', 'Organization')
    return Organization.user_organizations(user)


def publisher_url(user):
    """Returns appropriate publisher url according to current environment."""
    orgs = user_orgs(user)
    if orgs:
        return orgs.first().partner.publisher_url

    return None
