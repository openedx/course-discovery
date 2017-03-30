"""Tests API Serializers."""
import mock
from django.core import mail
from django.test import RequestFactory, TestCase
from opaque_keys.edx.keys import CourseKey
from rest_framework.exceptions import ValidationError

from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.core.tests.helpers import make_image_file
from course_discovery.apps.course_metadata.tests import toggle_switch
from course_discovery.apps.course_metadata.tests.factories import OrganizationFactory, PersonFactory
from course_discovery.apps.ietf_language_tags.models import LanguageTag
from course_discovery.apps.publisher.api.serializers import (CourseRevisionSerializer, CourseRunSerializer,
                                                             CourseRunStateSerializer, CourseStateSerializer,
                                                             CourseUserRoleSerializer, GroupUserSerializer)
from course_discovery.apps.publisher.choices import CourseRunStateChoices, CourseStateChoices, PublisherUserRole
from course_discovery.apps.publisher.models import CourseRun, CourseState, Seat
from course_discovery.apps.publisher.tests.factories import (CourseFactory, CourseRunFactory, CourseRunStateFactory,
                                                             CourseStateFactory, CourseUserRoleFactory,
                                                             OrganizationExtensionFactory, SeatFactory)


class CourseUserRoleSerializerTests(TestCase):
    serializer_class = CourseUserRoleSerializer

    def setUp(self):
        super(CourseUserRoleSerializerTests, self).setUp()
        self.request = RequestFactory()
        self.course_user_role = CourseUserRoleFactory(role=PublisherUserRole.MarketingReviewer)
        self.request.user = self.course_user_role.user

    def get_expected_data(self):
        """ Helper method which will return expected serialize data. """
        return {
            'course': self.course_user_role.course.id,
            'user': self.course_user_role.user.id,
            'role': self.course_user_role.role,
            'changed_by': self.course_user_role.user
        }

    def test_validation(self):
        """ Verify that serializer validate data. """

        # we are passing request to context because we need 'changed_by' user in validated values.
        serializer = self.serializer_class(self.course_user_role, context={'request': self.request})
        validated_data = serializer.validate(serializer.data)
        self.assertEqual(validated_data, self.get_expected_data())

    def test_update(self):
        """
        Test that user role assignment changed on update.
        """
        new_user = UserFactory()
        serializer = self.serializer_class(self.course_user_role, context={'request': self.request})
        course_role = serializer.update(self.course_user_role, {'user': new_user})
        self.assertEqual(course_role.user, new_user)
        self.assertEqual(len(mail.outbox), 1)

    def test_update_with_error(self):
        """
        Test that whole transaction roll backed if error in email sending.
        """
        new_user = UserFactory()
        serializer = self.serializer_class(self.course_user_role, context={'request': self.request})
        with mock.patch('django.core.mail.message.EmailMessage.send', side_effect=TypeError):
            with self.assertRaises(Exception):
                course_role = serializer.update(self.course_user_role, {'user': new_user})
                self.assertNotEqual(course_role.user, new_user)


class GroupUserSerializerTests(TestCase):

    def test_data_with_full_name(self):
        """ Verify that UserSerializer serialize the user object. """

        user = UserFactory(full_name='Test User')
        serializer = GroupUserSerializer(user)

        expected = {'id': user.id, 'full_name': user.full_name}
        self.assertDictEqual(serializer.data, expected)

    def test_data_without_full_name(self):
        """ Verify that UserSerializer serialize the user object using username
        if full_name is not available.
        """

        user = UserFactory(full_name='', first_name='', last_name='')
        serializer = GroupUserSerializer(user)

        expected = {'id': user.id, 'full_name': user.username}
        self.assertDictEqual(serializer.data, expected)


class CourseRunSerializerTests(TestCase):
    serializer_class = CourseRunSerializer

    def setUp(self):
        super(CourseRunSerializerTests, self).setUp()
        self.course_run = CourseRunFactory()
        self.course_run.lms_course_id = 'course-v1:edX+DemoX+Demo_Course'
        self.request = RequestFactory()
        self.user = UserFactory()
        self.request.user = self.user
        self.course_state = CourseRunStateFactory(course_run=self.course_run, owner_role=PublisherUserRole.Publisher)

    def get_expected_data(self):
        """ Helper method which will return expected serialize data. """
        return {
            'lms_course_id': self.course_run.lms_course_id,
            'changed_by': self.user,
            'preview_url': self.course_run.preview_url
        }

    def test_validate_lms_course_id(self):
        """ Verify that serializer raises error if 'lms_course_id' has invalid format. """
        self.course_run.lms_course_id = 'invalid-course-id'
        self.course_run.save()  # pylint: disable=no-member
        serializer = self.serializer_class(self.course_run)
        with self.assertRaises(ValidationError):
            serializer.validate_lms_course_id(self.course_run.lms_course_id)

    def test_validate_preview_url(self):
        """ Verify that serializer raises error if 'preview_url' has invalid format. """
        self.course_run.preview_url = 'invalid-preview-url'
        self.course_run.save()  # pylint: disable=no-member
        serializer = self.serializer_class(self.course_run)
        with self.assertRaises(ValidationError):
            serializer.validate_preview_url(self.course_run.preview_url)

    def test_serializer_with_valid_data(self):
        """ Verify that serializer validate course_run object. """
        serializer = self.serializer_class(self.course_run, context={'request': self.request})
        self.assertEqual(self.get_expected_data(), serializer.validate(serializer.data))

    def test_update_preview_url(self):
        """ Verify that course 'owner_role' will be changed to course_team after updating
        course run with preview url.
        """
        self.course_run.preview_url = ''
        self.course_run.save()
        serializer = self.serializer_class(self.course_run)
        serializer.update(self.course_run, {'preview_url': 'https://example.com/abc/course'})

        self.assertEqual(self.course_state.owner_role, PublisherUserRole.CourseTeam)
        self.assertEqual(self.course_run.preview_url, serializer.data['preview_url'])

    def test_update_lms_course_id(self):
        """ Verify that 'changed_by' also updated after updating course_run's lms_course_id."""
        self.course_run.preview_url = None
        self.course_run.save()

        serializer = self.serializer_class(self.course_run, context={'request': self.request})
        serializer.update(self.course_run, serializer.validate(serializer.data))

        self.assertEqual(self.course_run.lms_course_id, serializer.data['lms_course_id'])
        self.assertEqual(self.course_run.changed_by, self.user)

    def test_update_with_transaction_rollback(self):
        """
        Verify that transaction roll backed if an error occurred.
        """
        self.course_run.preview_url = ''
        self.course_run.save()
        serializer = self.serializer_class(self.course_run)

        with self.assertRaises(Exception):
            serializer.update(self.course_run, {'preview_url': 'invalid_url'})
            self.assertFalse(self.course_run.preview_url)

    def test_transaction_roll_back_with_error_on_email(self):
        """
        Verify that transaction is roll backed if error occurred during email sending.
        """
        toggle_switch('enable_publisher_email_notifications', True)
        self.course_run.preview_url = ''
        self.course_run.save()
        serializer = self.serializer_class(self.course_run)
        self.assertEqual(self.course_run.course_run_state.owner_role, PublisherUserRole.Publisher)

        with self.assertRaises(Exception):
            serializer.update(self.course_run, {'preview_url': 'https://example.com/abc/course'})

        self.course_run = CourseRun.objects.get(id=self.course_run.id)
        self.assertFalse(self.course_run.preview_url)
        # Verify that owner role not changed.
        self.assertEqual(self.course_run.course_run_state.owner_role, PublisherUserRole.Publisher)


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
            'level_type': revision.level_type.name,
            'learner_testimonial': revision.learner_testimonial,
            'faq': revision.faq,
            'video_link': revision.video_link
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
            'level_type': None,
            'learner_testimonial': revision.learner_testimonial,
            'faq': revision.faq,
            'video_link': revision.video_link
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
        organization = OrganizationFactory()
        self.course_run.course.organizations.add(organization)
        self.course_run.save()
        self.course_run.staff.add(PersonFactory())

        toggle_switch('enable_publisher_email_notifications', True)
        CourseUserRoleFactory(
            course=self.course_run.course, role=PublisherUserRole.CourseTeam, user=self.user
        )
        CourseUserRoleFactory(
            course=self.course_run.course, role=PublisherUserRole.ProjectCoordinator, user=UserFactory()
        )

    def test_update(self):
        """
        Verify that we can update course-run workflow state name and preview_accepted with serializer.
        """
        CourseUserRoleFactory(
            course=self.course_run.course, role=PublisherUserRole.Publisher, user=UserFactory()
        )

        self.assertNotEqual(self.run_state, CourseRunStateChoices.Review)

        self.course_run.lms_course_id = 'course-v1:edX+DemoX+Demo_Course'
        serializer = self.serializer_class(self.run_state, context={'request': self.request})
        data = {'name': CourseRunStateChoices.Review}
        serializer.update(self.run_state, data)

        self.assertEqual(self.run_state.name, CourseRunStateChoices.Review)
        self.assertEqual(len(mail.outbox), 1)

        course_key = CourseKey.from_string(self.course_run.lms_course_id)
        subject = 'Review requested: {course_name} {run_name}'.format(
            course_name=self.course_run.course.title,
            run_name=course_key.run
        )
        self.assertIn(subject, str(mail.outbox[0].subject))

        self.assertFalse(self.run_state.preview_accepted)
        serializer.update(self.run_state, {'preview_accepted': True})

        self.assertEqual(len(mail.outbox), 2)
        subject = 'Publication requested: {course_name} {run_name}'.format(
            course_name=self.course_run.course.title,
            run_name=course_key.run
        )
        self.assertIn(subject, str(mail.outbox[1].subject))

    def test_update_with_error(self):
        """
        Verify that serializer raises `ValidationError` with wrong transition.
        """
        serializer = self.serializer_class(self.run_state, context={'request': self.request})
        data = {'name': CourseRunStateChoices.Published}

        with self.assertRaises(ValidationError):
            serializer.update(self.run_state, data)
            self.assertEqual(len(mail.outbox), 1)

    def test_update_with_transaction_roll_back(self):
        """
        Verify that transaction roll back all db changes.
        """
        self.assertNotEqual(self.run_state, CourseRunStateChoices.Review)
        serializer = self.serializer_class(self.run_state, context={'request': self.request})
        data = {'name': CourseRunStateChoices.Review}
        with self.assertRaises(Exception):
            serializer.update(self.run_state, data)
            self.assertEqual(self.run_state.name, CourseRunStateChoices.Review)

            self.assertFalse(self.run_state.preview_accepted)
            serializer.update(self.run_state, {'preview_accepted': True})

            self.assertFalse(CourseRun.objects.get(id=self.course_run.id).preview_url)
            self.assertEqual(len(mail.outbox), 0)
