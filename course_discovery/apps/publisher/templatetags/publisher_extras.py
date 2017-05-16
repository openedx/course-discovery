from django import template

from course_discovery.apps.publisher.mixins import check_course_organization_permission
from course_discovery.apps.publisher.models import OrganizationExtension
from course_discovery.apps.publisher.utils import has_role_for_course

register = template.Library()


def can_edit(course, user, permission):
    return check_course_organization_permission(
        user, course, permission
    ) and has_role_for_course(course, user)


@register.filter
def can_edit_course(course, user):
    return can_edit(course, user, OrganizationExtension.EDIT_COURSE)
