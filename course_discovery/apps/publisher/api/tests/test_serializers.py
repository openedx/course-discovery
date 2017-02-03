"""Tests API Serializers."""
from django.test import RequestFactory, TestCase
from rest_framework.exceptions import ValidationError

from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.publisher.api.serializers import (
    CourseUserRoleSerializer, GroupUserSerializer, UpdateCourseKeySerializer, CourseRevisionSerializer,
    CourseStateSerializer, CourseRunStateSerializer
)
from course_discovery.apps.publisher.choices import CourseStateChoices, CourseRunStateChoices
from course_discovery.apps.publisher.models import CourseState, CourseRunState
from course_discovery.apps.publisher.tests.factories import (
    CourseFactory, CourseRunFactory, CourseRunStateFactory, CourseStateFactory, CourseUserRoleFactory
)


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


class CourseRevisionSerializerTests(TestCase):
    def test_course_revision_serializer(self):
        """ Verify that CourseRevisionSerializer serialize the course revision object. """

        course = CourseFactory()
        course.title = 'updated title'
        course.save()
        revision = course.history.first()
        serializer = CourseRevisionSerializer(revision)

        expected = {
            'history_id': revision.history_id,
            'title': revision.title,
            'number': revision.number,
            'short_description': revision.short_description,
            'full_description': revision.full_description,
            'expected_learnings': revision.expected_learnings,
            'prerequisites': revision.prerequisites,
            'primary_subject': revision.primary_subject.name,
            'secondary_subject': revision.secondary_subject.name,
            'tertiary_subject': revision.tertiary_subject.name,
            'level_type': revision.level_type.name
        }

        self.assertDictEqual(serializer.data, expected)

    def test_course_revision_serializer_without_subjects(self):
        """ Verify that CourseRevisionSerializer serialize the course revision object
        even if subject fields are not available.
        """

        course = CourseFactory(primary_subject=None, secondary_subject=None, tertiary_subject=None, level_type=None)
        course.title = 'updated title'
        course.save()
        revision = course.history.first()
        serializer = CourseRevisionSerializer(revision)

        expected = {
            'history_id': revision.history_id,
            'title': revision.title,
            'number': revision.number,
            'short_description': revision.short_description,
            'full_description': revision.full_description,
            'expected_learnings': revision.expected_learnings,
            'prerequisites': revision.prerequisites,
            'primary_subject': None,
            'secondary_subject': None,
            'tertiary_subject': None,
            'level_type': None
        }

        self.assertDictEqual(serializer.data, expected)


class CourseStateSerializerTests(TestCase):
    serializer_class = CourseStateSerializer

    def setUp(self):
        super(CourseStateSerializerTests, self).setUp()
        self.course_state = CourseStateFactory(name=CourseStateChoices.Draft)

    def test_update(self):
        """
        Verify that we can update course workflow state with serializer.
        """
        self.assertNotEqual(self.course_state, CourseStateChoices.Review)
        serializer = self.serializer_class(self.course_state)
        data = {'name': CourseStateChoices.Review}
        serializer.update(self.course_state, data)

        self.course_state = CourseState.objects.get(course=self.course_state.course)
        self.assertEqual(self.course_state.name, CourseStateChoices.Review)

    def test_update_with_error(self):
        """
        Verify that serializer raises `ValidationError` with wrong transition.
        """
        serializer = self.serializer_class(self.course_state)
        data = {'name': CourseStateChoices.Approved}

        with self.assertRaises(ValidationError):
            serializer.update(self.course_state, data)


class CourseRunStateSerializerTests(TestCase):
    serializer_class = CourseRunStateSerializer

    def setUp(self):
        super(CourseRunStateSerializerTests, self).setUp()
        self.run_state = CourseRunStateFactory(name=CourseRunStateChoices.Draft)

    def test_update(self):
        """
        Verify that we can update course-run workflow state with serializer.
        """
        self.assertNotEqual(self.run_state, CourseRunStateChoices.Review)
        serializer = self.serializer_class(self.run_state)
        data = {'name': CourseRunStateChoices.Review}
        serializer.update(self.run_state, data)

        self.run_state = CourseRunState.objects.get(course_run=self.run_state.course_run)
        self.assertEqual(self.run_state.name, CourseRunStateChoices.Review)

    def test_update_with_error(self):
        """
        Verify that serializer raises `ValidationError` with wrong transition.
        """
        serializer = self.serializer_class(self.run_state)
        data = {'name': CourseRunStateChoices.Published}

        with self.assertRaises(ValidationError):
            serializer.update(self.run_state, data)
