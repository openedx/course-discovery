"""Tests API Serializers."""
from unittest import TestCase

from django.test import RequestFactory

from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.publisher.api.serializers import CourseUserRoleSerializer, GroupUserSerializer
from course_discovery.apps.publisher.tests.factories import CourseUserRoleFactory


class CourseUserRoleSerializerTests(TestCase):
    serializer_class = CourseUserRoleSerializer

    def setUp(self):
        super(CourseUserRoleSerializerTests, self).setUp()
        self.request = RequestFactory()
        self.course_user_role = CourseUserRoleFactory()
        self.request.user = self.course_user_role.user

    def get_expected_data(self):
        return {
            'course': self.course_user_role.course.id,
            'user': self.course_user_role.user.id,
            'role': self.course_user_role.role,
            'changed_by': self.course_user_role.user
        }

    def test_validation(self):
        serializer = self.serializer_class(self.course_user_role, context={'request': self.request})
        validated_data = serializer.validate(serializer.data)
        self.assertEqual(validated_data, self.get_expected_data())


class GroupUserSerializerTests(TestCase):
    def test_date(self):
        """ Verify that UserSerializer serialize the user object. """

        user = UserFactory(full_name="test user")
        serializer = GroupUserSerializer(user)

        self.assertDictEqual(serializer.data, {'id': user.id, 'full_name': user.full_name})
