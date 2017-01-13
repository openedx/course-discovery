"""Tests API Serializers."""
from django.test import RequestFactory, TestCase
from rest_framework.exceptions import ValidationError

from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.publisher.api.serializers import (
    CourseUserRoleSerializer, GroupUserSerializer, UpdateCourseKeySerializer
)
from course_discovery.apps.publisher.tests.factories import CourseUserRoleFactory, CourseRunFactory


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


class UpdateCourseKeySerializerTests(TestCase):
    serializer_class = UpdateCourseKeySerializer

    def setUp(self):
        super(UpdateCourseKeySerializerTests, self).setUp()
        self.course_run = CourseRunFactory()
        self.request = RequestFactory()
        self.user = UserFactory()
        self.request.user = self.user

    def get_expected_data(self):
        return {
            'lms_course_id': self.course_run.lms_course_id,
            'changed_by': self.user
        }

    def test_validation(self):
        self.course_run.lms_course_id = 'course-v1:edxTest+TC101+2016_Q1'
        self.course_run.save()  # pylint: disable=no-member
        serializer = self.serializer_class(self.course_run, context={'request': self.request})
        expected = serializer.validate(serializer.data)
        self.assertEqual(self.get_expected_data(), expected)

    def test_validation_error(self):
        self.course_run.lms_course_id = 'invalid-course-id'
        self.course_run.save()  # pylint: disable=no-member
        serializer = self.serializer_class(self.course_run)
        with self.assertRaises(ValidationError):
            serializer.validate(serializer.data)
