"""
Publisher courses serializers.
"""
from django.core.exceptions import ObjectDoesNotExist
from django.urls import reverse
from django.utils.translation import ugettext as _
from rest_framework import serializers

from course_discovery.apps.publisher.mixins import check_course_organization_permission
from course_discovery.apps.publisher.models import OrganizationExtension
from course_discovery.apps.publisher.utils import has_role_for_course


class CourseSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """
    Publisher courses list serializer.
    """
    course_title = serializers.SerializerMethodField()
    organization_name = serializers.SerializerMethodField()
    project_coordinator_name = serializers.SerializerMethodField()
    publisher_course_runs_count = serializers.SerializerMethodField()
    course_team_status = serializers.SerializerMethodField()
    internal_user_status = serializers.SerializerMethodField()
    edit_url = serializers.SerializerMethodField()

    def get_course_title(self, course):
        """
        Returns a dict containing course `title` and `url`.
        """
        publisher_hide_features_for_pilot = self.context['publisher_hide_features_for_pilot']
        return {
            'title': course.title,
            'url': None if publisher_hide_features_for_pilot else reverse(
                'publisher:publisher_course_detail', kwargs={'pk': course.id}
            )
        }

    def get_organization_name(self, course):
        """
        Returns course organization name.
        """
        return course.organization_name

    def get_project_coordinator_name(self, course):
        """
        Returns course project coordinator name.
        """
        project_coordinator = course.project_coordinator
        return project_coordinator.full_name if project_coordinator else ''

    def get_publisher_course_runs_count(self, course):
        """
        Returns count of course runs for a course.
        """
        try:
            return course.publisher_course_runs.count()
        except ObjectDoesNotExist:
            return 0

    def get_course_team_status(self, course):
        """
        Returns a dict containing `status` and `date` for course team status.
        """
        default_status = {
            'status': '',
            'date': ''
        }

        try:
            course_team_status = course.course_state.course_team_status
        except ObjectDoesNotExist:
            return default_status

        course_team_status = default_status if course_team_status is None else course_team_status
        course_team_status_date = course_team_status.get('date', '')
        return {
            'status': course_team_status.get('status_text', ''),
            'date': course_team_status_date and course_team_status_date.strftime('%m/%d/%y')
        }

    def get_internal_user_status(self, course):
        """
        Returns a dict containing `status` and `date` for internal user status.
        """
        default_status = {
            'status': '',
            'date': ''
        }

        try:
            internal_user_status = course.course_state.internal_user_status
        except ObjectDoesNotExist:
            return default_status

        internal_user_status = default_status if internal_user_status is None else internal_user_status
        internal_user_status_date = internal_user_status.get('date', '')
        return {
            'status': internal_user_status.get('status_text', ''),
            'date': internal_user_status_date and internal_user_status_date.strftime('%m/%d/%y')
        }

    def get_edit_url(self, course):
        """
        Returns a dict containing `title` and `url` to edit a course.
        """
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
        """
        Check if user has permissions on course.

        Arguments:
            course: course instance to be serialized
            user: currently logedin user

        Returns:
            bool: Whether the logedin user has permission or not.
        """
        try:
            return check_course_organization_permission(
                user, course, OrganizationExtension.EDIT_COURSE
            ) and has_role_for_course(course, user)
        except ObjectDoesNotExist:
            return False
