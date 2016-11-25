"""Tests Publisher Serializers."""
from unittest import TestCase

from django.test import RequestFactory
from rest_framework.exceptions import ValidationError

from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.publisher.serializers import UpdateCourseKeySerializer
from course_discovery.apps.publisher.tests.factories import CourseRunFactory


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
        self.course_run.lms_course_id = 'wrong-course-id'
        self.course_run.save()  # pylint: disable=no-member
        serializer = self.serializer_class(self.course_run)
        with self.assertRaises(ValidationError):
            serializer.validate(serializer.data)
