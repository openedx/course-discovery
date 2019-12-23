"""
Publisher courses serializers.
"""
from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import ugettext as _
from rest_framework import serializers

from course_discovery.apps.core.utils import serialize_datetime
from course_discovery.apps.publisher.mixins import check_course_organization_permission
from course_discovery.apps.publisher.models import OrganizationExtension
from course_discovery.apps.publisher.utils import has_role_for_course


class CourseSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    course_title = serializers.SerializerMethodField()
    number = serializers.SerializerMethodField()
    organization_name = serializers.SerializerMethodField()
    project_coordinator_name = serializers.SerializerMethodField()
    publisher_course_runs_count = serializers.SerializerMethodField()
    course_team_status = serializers.SerializerMethodField()
    internal_user_status = serializers.SerializerMethodField()
    edit_url = serializers.SerializerMethodField()
    last_state_change = serializers.SerializerMethodField()

    def get_number(self, course):
        return course.number

    def get_course_title(self, course):
        return {
            'title': course.title,
            'url': None,
        }

    def get_organization_name(self, course):
        return course.organization_name

    def get_project_coordinator_name(self, course):
        project_coordinator = course.project_coordinator
        return project_coordinator.full_name if project_coordinator else ''

    def get_publisher_course_runs_count(self, course):
        try:
            return course.publisher_course_runs.count()
        except ObjectDoesNotExist:
            return 0

    def get_course_team_status(self, course):
        try:
            return course.course_state.course_team_status
        except ObjectDoesNotExist:
            return ''

    def get_internal_user_status(self, course):
        try:
            return course.course_state.internal_user_status
        except ObjectDoesNotExist:
            return ''

    def get_last_state_change(self, course):
        return serialize_datetime(course.course_state.owner_role_modified)

    def get_edit_url(self, _course):
        return {
            'title': _('Edit'),
            'url': None,
        }

    @classmethod
    def can_edit_course(cls, course, user):
        try:
            return check_course_organization_permission(
                user, course, OrganizationExtension.EDIT_COURSE
            ) and has_role_for_course(course, user)
        except ObjectDoesNotExist:
            return False
