"""Tests API Serializers."""
from django.test import RequestFactory, TestCase
from rest_framework.exceptions import ValidationError

from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.core.tests.helpers import make_image_file
from course_discovery.apps.course_metadata.tests.factories import PersonFactory
from course_discovery.apps.ietf_language_tags.models import LanguageTag
from course_discovery.apps.publisher.api.serializers import (CourseRevisionSerializer, CourseRunStateSerializer,
                                                             CourseStateSerializer, CourseUserRoleSerializer,
                                                             GroupUserSerializer, UpdateCourseKeySerializer)
from course_discovery.apps.publisher.choices import CourseRunStateChoices, CourseStateChoices, PublisherUserRole
from course_discovery.apps.publisher.models import CourseState, Seat
from course_discovery.apps.publisher.tests.factories import (CourseFactory, CourseRunFactory, CourseRunStateFactory,
                                                             CourseStateFactory, CourseUserRoleFactory,
                                                             OrganizationExtensionFactory, SeatFactory)


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

    def test_data_with_full_name(self):
        """ Verify that UserSerializer serialize the user object. """

        user = UserFactory(full_name='Test User')
        serializer = GroupUserSerializer(user)

        expected = {'id': user.id, 'full_name': user.full_name}
        self.assertDictEqual(serializer.data, expected)

    def test_data_without_full_name(self):
        """ Verify that UserSerializer serialize the user object. """

        user = UserFactory(full_name='', first_name='', last_name='')
        serializer = GroupUserSerializer(user)

        expected = {'id': user.id, 'full_name': user.username}
        self.assertDictEqual(serializer.data, expected)


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
        self.request = RequestFactory()
        self.user = UserFactory()
        self.request.user = self.user

        CourseUserRoleFactory(
            course=self.course_state.course, role=PublisherUserRole.CourseTeam, user=self.user
        )

    def test_update(self):
        """
        Verify that we can update course workflow state with serializer.
        """
        course = self.course_state.course
        course.image = make_image_file('test_banner.jpg')
        course.save()
        course.organizations.add(OrganizationExtensionFactory().organization)

        self.assertNotEqual(self.course_state, CourseStateChoices.Review)
        serializer = self.serializer_class(self.course_state, context={'request': self.request})
        data = {'name': CourseStateChoices.Review}
        serializer.update(self.course_state, data)

        self.course_state = CourseState.objects.get(course=self.course_state.course)
        self.assertEqual(self.course_state.name, CourseStateChoices.Review)
        self.assertEqual(self.course_state.owner_role, PublisherUserRole.MarketingReviewer)

    def test_update_with_error(self):
        """
        Verify that serializer raises `ValidationError` with wrong transition.
        """
        serializer = self.serializer_class(self.course_state, context={'request': self.request})
        data = {'name': CourseStateChoices.Approved}

        with self.assertRaises(ValidationError):
            serializer.update(self.course_state, data)


class CourseRunStateSerializerTests(TestCase):
    serializer_class = CourseRunStateSerializer

    def setUp(self):
        super(CourseRunStateSerializerTests, self).setUp()
        self.run_state = CourseRunStateFactory(name=CourseRunStateChoices.Draft)
        self.course_run = self.run_state.course_run
        self.request = RequestFactory()
        self.user = UserFactory()
        self.request.user = self.user
        CourseStateFactory(name=CourseStateChoices.Approved, course=self.course_run.course)

        SeatFactory(course_run=self.course_run, type=Seat.AUDIT)
        language_tag = LanguageTag(code='te-st', name='Test Language')
        language_tag.save()
        self.course_run.transcript_languages.add(language_tag)
        self.course_run.language = language_tag
        self.course_run.save()
        self.course_run.staff.add(PersonFactory())

    def test_update(self):
        """
        Verify that we can update course-run workflow state name and preview_accepted with serializer.
        """
        CourseUserRoleFactory(
            course=self.course_run.course, role=PublisherUserRole.CourseTeam, user=self.user
        )

        self.assertNotEqual(self.run_state, CourseRunStateChoices.Review)
        serializer = self.serializer_class(self.run_state, context={'request': self.request})
        data = {'name': CourseRunStateChoices.Review}
        serializer.update(self.run_state, data)

        self.assertEqual(self.run_state.name, CourseRunStateChoices.Review)

        self.assertFalse(self.run_state.preview_accepted)
        serializer.update(self.run_state, {'preview_accepted': True})

        self.assertTrue(self.run_state.preview_accepted)

    def test_update_with_error(self):
        """
        Verify that serializer raises `ValidationError` with wrong transition.
        """
        serializer = self.serializer_class(self.run_state, context={'request': self.request})
        data = {'name': CourseRunStateChoices.Published}

        with self.assertRaises(ValidationError):
            serializer.update(self.run_state, data)
