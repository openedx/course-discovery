"""Tests API Serializers."""
import mock
from django.test import RequestFactory, TestCase
from rest_framework.exceptions import ValidationError
from waffle.testutils import override_switch

from course_discovery.apps.api.tests.mixins import SiteMixin
from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.core.tests.helpers import make_image_file
from course_discovery.apps.course_metadata.tests.factories import CourseRunFactory as DiscoveryCourseRunFactory
from course_discovery.apps.course_metadata.tests.factories import OrganizationFactory, PersonFactory
from course_discovery.apps.ietf_language_tags.models import LanguageTag
from course_discovery.apps.publisher.api.serializers import (
    CourseRevisionSerializer, CourseRunSerializer, CourseRunStateSerializer, CourseStateSerializer,
    CourseUserRoleSerializer, GroupUserSerializer, OrganizationUserRoleSerializer
)
from course_discovery.apps.publisher.choices import CourseRunStateChoices, CourseStateChoices, PublisherUserRole
from course_discovery.apps.publisher.models import CourseRun, CourseState, Seat
from course_discovery.apps.publisher.tests.factories import (
    CourseFactory, CourseRunFactory, CourseRunStateFactory, CourseStateFactory, CourseUserRoleFactory,
    OrganizationExtensionFactory, OrganizationUserRoleFactory, SeatFactory
)


class CourseUserRoleSerializerTests(SiteMixin, TestCase):
    serializer_class = CourseUserRoleSerializer

    def setUp(self):
        super(CourseUserRoleSerializerTests, self).setUp()
        self.request = RequestFactory()
        self.course_user_role = CourseUserRoleFactory(role=PublisherUserRole.MarketingReviewer)
        self.request.user = self.course_user_role.user
        self.request.site = self.site

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


class GroupUserSerializerTests(TestCase):

    def test_data_with_full_name(self):
        """ Verify that UserSerializer serialize the user object. """

        user = UserFactory(full_name='Test User')
        serializer = GroupUserSerializer(user)

        expected = {'id': user.id, 'full_name': user.full_name, 'email': user.email}
        self.assertDictEqual(serializer.data, expected)

    def test_data_without_full_name(self):
        """ Verify that UserSerializer serialize the user object using username
        if full_name is not available.
        """

        user = UserFactory(full_name='', first_name='', last_name='')
        serializer = GroupUserSerializer(user)

        expected = {'id': user.id, 'full_name': user.username, 'email': user.email}
        self.assertDictEqual(serializer.data, expected)


class OrganizationUserRoleSerializerTests(TestCase):
    def test_basic_serialization(self):
        role = OrganizationUserRoleFactory()
        serializer = OrganizationUserRoleSerializer(role)

        expected = {'id': role.id, 'role': role.role, 'user': GroupUserSerializer(role.user).data}
        self.assertDictEqual(serializer.data, expected)


class CourseRunSerializerTests(TestCase):
    serializer_class = CourseRunSerializer

    def setUp(self):
        super(CourseRunSerializerTests, self).setUp()
        self.course_run = CourseRunFactory()
        self.course_run.lms_course_id = 'course-v1:edX+DemoX+Demo_Course'
        self.course_run.external_key = 'testOrg-course-1'
        self.person = PersonFactory()
        self.discovery_course_run = DiscoveryCourseRunFactory(
            key=self.course_run.lms_course_id,
            external_key=self.course_run.external_key,
            staff=[self.person])
        self.request = RequestFactory()
        self.user = UserFactory()
        self.request.user = self.user
        self.course_state = CourseRunStateFactory(course_run=self.course_run, owner_role=PublisherUserRole.Publisher)

    def get_expected_data(self):
        """ Helper method which will return expected serialize data. """
        return {
            'lms_course_id': self.course_run.lms_course_id,
            'changed_by': self.user,
            'preview_url': self.course_run.preview_url,
            'external_key': self.course_run.external_key,
        }

    def test_validate_lms_course_id(self):
        """ Verify that serializer raises error if 'lms_course_id' has invalid format. """
        self.course_run.lms_course_id = 'invalid-course-id'
        self.course_run.save()
        serializer = self.serializer_class(self.course_run)
        with self.assertRaises(ValidationError):
            serializer.validate_lms_course_id(self.course_run.lms_course_id)

    def test_validate_external_lms_course_id(self):
        """ Verify that serializer raises error if 'external_key' has invalid format. """
        self.course_run.external_key = '~~!bad#$&*key~~'
        self.course_run.save()
        serializer = self.serializer_class(self.course_run)
        with self.assertRaises(ValidationError):
            serializer.validate_external_key(self.course_run.external_key)

    def test_validate_preview_url(self):
        """ Verify that serializer raises error if 'preview_url' has invalid format. """
        serializer = self.serializer_class(self.course_run, context={'request': self.request})
        with self.assertRaises(ValidationError):
            serializer.validate({'preview_url': 'invalid-url'})

    def test_serializer_with_valid_data(self):
        """ Verify that serializer validate course_run object. """
        serializer = self.serializer_class(self.course_run, context={'request': self.request})
        self.assertEqual(self.get_expected_data(), serializer.validate(serializer.data))

    def test_update_preview_url(self):
        """ Verify that course 'owner_role' will be changed to course_team after updating
        course run with preview url.
        """
        self.discovery_course_run.slug = ''
        self.discovery_course_run.save(suppress_publication=True)
        serializer = self.serializer_class(self.course_run, context={'request': self.request})
        serializer.update(self.course_run, {'preview_url': 'https://example.com/abc/course'})

        self.assertEqual(self.course_state.owner_role, PublisherUserRole.CourseTeam)
        self.assertEqual(self.course_run.preview_url.rsplit('/', 1)[-1], 'course')

    @override_switch('publish_course_runs_to_marketing_site', True)
    def test_update_preview_url_no_op(self):
        """ Verify we don't push to marketing if no change required """
        self.discovery_course_run.slug = ''
        self.discovery_course_run.save(suppress_publication=True)

        serializer = self.serializer_class(self.course_run, context={'request': self.request})

        mock_path = 'course_discovery.apps.course_metadata.publishers.CourseRunMarketingSitePublisher.publish_obj'
        with mock.patch(mock_path) as mock_save:
            serializer.update(self.course_run, {'preview_url': 'https://example.com/abc/course'})
            self.assertEqual(mock_save.call_count, 1)

            # Now when we update a second time, there should be nothing to do, call count should remain at 1
            serializer.update(self.course_run, {'preview_url': 'https://example.com/abc/course'})
            self.assertEqual(mock_save.call_count, 1)

    def test_update_preview_url_slug_exists(self):
        """ Verify we don't push to marketing if no change required """
        DiscoveryCourseRunFactory(title='course')  # will create the slug 'course'
        serializer = self.serializer_class(self.course_run, context={'request': self.request})

        with self.assertRaises(Exception) as cm:
            serializer.update(self.course_run, {'preview_url': 'https://example.com/abc/course'})
        self.assertEqual(cm.exception.args[0], 'Preview URL already in use for another course')

    def test_update_lms_course_id(self):
        """ Verify that 'changed_by' also updated after updating course_run's lms_course_id."""
        serializer = self.serializer_class(self.course_run, context={'request': self.request})
        serializer.update(self.course_run, serializer.validate(serializer.data))

        self.assertEqual(self.course_run.lms_course_id, serializer.data['lms_course_id'])
        self.assertEqual(self.course_run.changed_by, self.user)

    def test_update_with_transaction_rollback(self):
        """
        Verify that transaction roll backed if an error occurred.
        """
        serializer = self.serializer_class(self.course_run)

        with self.assertRaises(Exception):
            serializer.update(self.course_run, {'preview_url': 'invalid_url'})
            self.assertFalse(self.course_run.preview_url)


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


class CourseStateSerializerTests(SiteMixin, TestCase):
    serializer_class = CourseStateSerializer

    def setUp(self):
        super(CourseStateSerializerTests, self).setUp()
        self.course_state = CourseStateFactory(name=CourseStateChoices.Draft)
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


class CourseRunStateSerializerTests(SiteMixin, TestCase):
    serializer_class = CourseRunStateSerializer

    def setUp(self):
        super(CourseRunStateSerializerTests, self).setUp()
        self.run_state = CourseRunStateFactory(name=CourseRunStateChoices.Draft)
        self.course_run = self.run_state.course_run
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
        self.assertFalse(self.run_state.preview_accepted)
        serializer.update(self.run_state, {'preview_accepted': True})

    def test_update_with_error(self):
        """
        Verify that serializer raises `ValidationError` with wrong transition.
        """
        serializer = self.serializer_class(self.run_state, context={'request': self.request})
        data = {'name': CourseRunStateChoices.Published}

        with self.assertRaises(ValidationError):
            serializer.update(self.run_state, data)

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
