import ddt
import six
from django.conf import settings
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from pytest import mark
from taxonomy.models import CourseSkills

from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.course_metadata.constants import COURSE_SKILLS_URL_NAME
from course_discovery.apps.course_metadata.tests.factories import CourseFactory, CourseSkillsFactory
from course_discovery.apps.course_metadata.views import CourseSkillsView


@ddt.ddt
@mark.django_db
@override_settings(ROOT_URLCONF="course_discovery.urls")
class TestCourseSkillView(TestCase):
    """
    Tests for CourseSkillView GET endpoint.
    """
    def setUp(self):
        """
        Test set up
        """
        super().setUp()
        self.user = UserFactory.create(is_staff=True, is_active=True)
        self.user.set_password('QWERTY')
        self.user.save()
        self.course = CourseFactory()
        self.admin_context = {
            'has_permission': True,
            'opts': self.course._meta,
        }
        self.client = Client()
        self.view_url = reverse(
            "admin:" + COURSE_SKILLS_URL_NAME,
            args=(self.course.pk,)
        )
        self.context_parameters = CourseSkillsView.ContextParameters

    def _login(self):
        """Log user in."""
        assert self.client.login(username=self.user.username, password='QWERTY')

    def _test_admin_context(self, actual_context):
        """Test admin context."""
        expected_context = {}
        expected_context.update(self.admin_context)

        for context_key, expected_value in six.iteritems(expected_context):
            assert actual_context[context_key] == expected_value

    def _test_get_response(self, response, course_skills):
        """Test view GET response."""
        if course_skills:
            skills_name = [course_skill.skill.name for course_skill in course_skills]
            # get sorted list of skills to match it with API results
            sorted_skill_names = list(CourseSkills.objects.filter(
                skill__name__in=skills_name
            ))
        else:
            sorted_skill_names = course_skills
        assert response.status_code == 200
        self._test_admin_context(response.context)
        assert list(response.context[self.context_parameters.COURSE_SKILLS]) == sorted_skill_names
        assert response.context[self.context_parameters.COURSE] == self.course

    def _create_course_skills(self, course):
        """Create dummy course skills."""
        course_skill1 = CourseSkillsFactory(course_id=course.key)
        course_skill2 = CourseSkillsFactory(course_id=course.key)
        return [course_skill1, course_skill2]

    def test_get_user_not_logged_in(self):
        """Tests response if user is not logged in."""
        assert settings.SESSION_COOKIE_NAME not in self.client.cookies  # precondition check - no session cookie
        response = self.client.get(self.view_url)
        assert response.status_code == 302

    def test_get_no_course_skills(self):
        """Tests response when a course has no skills."""
        self._login()
        response = self.client.get(self.view_url)
        self._test_get_response(response, [])

    def test_get_course_skills(self):
        """Tests if course skills are returned in response correctly."""
        self._login()
        course_skills = self._create_course_skills(self.course)
        response = self.client.get(self.view_url)
        self._test_get_response(response, course_skills)
