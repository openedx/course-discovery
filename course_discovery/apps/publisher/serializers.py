"""
Publisher courses serializers.
"""
from django.core.exceptions import ObjectDoesNotExist
from django.urls import reverse
from django.utils.translation import ugettext as _
from rest_framework import serializers

from course_discovery.apps.core.utils import serialize_datetime
from course_discovery.apps.publisher.mixins import check_course_organization_permission
from course_discovery.apps.publisher.models import OrganizationExtension
from course_discovery.apps.publisher.utils import has_role_for_course


class CourseSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    course_title = serializers.SerializerMethodField()
    publisher_course_runs_count = serializers.SerializerMethodField()
    course_team_status = serializers.SerializerMethodField()
    internal_user_status = serializers.SerializerMethodField()
    edit_url = serializers.SerializerMethodField()
    last_state_change = serializers.SerializerMethodField()

    def get_course_title(self, course):
        publisher_hide_features_for_pilot = self.context['publisher_hide_features_for_pilot']
        return {
            'title': course.title,
            'url': None if publisher_hide_features_for_pilot else reverse(
                'publisher:publisher_course_detail', kwargs={'pk': course.id}
            )
        }

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

    def get_edit_url(self, course):
        courses_edit_url = None
        publisher_hide_features_for_pilot = self.context['publisher_hide_features_for_pilot']
        if not publisher_hide_features_for_pilot and self.can_edit_course(course, self.context['user']):
            courses_edit_url = reverse('publisher:publisher_courses_edit', kwargs={'pk': course.id})

        return {
            'title': _('Edit'),
            'url': courses_edit_url
        }

    @classmethod
    def can_edit_course(cls, course, user):
        try:
            return check_course_organization_permission(
                user, course, OrganizationExtension.EDIT_COURSE
            ) and has_role_for_course(course, user)
        except ObjectDoesNotExist:
            return False
