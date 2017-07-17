# pylint: disable=no-member
import ddt
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from django_fsm import TransitionNotAllowed
from guardian.shortcuts import assign_perm

from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.core.tests.helpers import make_image_file
from course_discovery.apps.course_metadata.tests.factories import OrganizationFactory, PersonFactory
from course_discovery.apps.ietf_language_tags.models import LanguageTag
from course_discovery.apps.publisher.choices import CourseRunStateChoices, CourseStateChoices, PublisherUserRole
from course_discovery.apps.publisher.mixins import check_course_organization_permission
from course_discovery.apps.publisher.models import CourseUserRole, OrganizationExtension, OrganizationUserRole, Seat
from course_discovery.apps.publisher.tests import factories


@ddt.ddt
class CourseRunTests(TestCase):
    """ Tests for the publisher `CourseRun` model. """

    @classmethod
    def setUpClass(cls):
        super(CourseRunTests, cls).setUpClass()
        cls.course_run = factories.CourseRunFactory()

    def test_str(self):
        """ Verify casting an instance to a string returns a string containing the course title and start date. """
        self.assertEqual(
            str(self.course_run),
            '{title}: {date}'.format(
                title=self.course_run.course.title, date=self.course_run.start
            )
        )

    def test_post_back_url(self):
        self.assertEqual(
            self.course_run.post_back_url,
            reverse('publisher:publisher_course_runs_edit', kwargs={'pk': self.course_run.id})
        )

    def test_created_by(self):
        """ Verify that property returns created_by. """
        self.assertIsNone(self.course_run.created_by)

        user = UserFactory()
        history_object = self.course_run.history.first()
        history_object.history_user = user
        history_object.save()

        self.assertEqual(self.course_run.created_by, user.get_full_name())

    def test_studio_url(self):
        """ Verify that property returns studio url. """
        self.assertFalse(self.course_run.studio_url)

        # save the lms course id and save the organization.
        self.course_run.lms_course_id = 'test'
        self.course_run.save()
        organization = OrganizationFactory()
        self.course_run.course.organizations.add(organization)
        self.assertEqual(self.course_run.course.partner, organization.partner)

        self.assertEqual(
            '{url}/course/{id}'.format(url=self.course_run.course.partner.studio_url, id='test'),
            self.course_run.studio_url
        )

    def test_has_valid_staff(self):
        """ Verify that property returns True if course-run must have a staff member
        with bio and image.
        """
        self.assertFalse(self.course_run.has_valid_staff)
        staff = PersonFactory()
        self.course_run.staff.add(staff)
        self.assertTrue(self.course_run.has_valid_staff)

    @ddt.data('bio', 'profile_image')
    def test_with_in_valid_staff(self, field):
        """ Verify that property returns False staff has bio or image is missing."""
        staff = PersonFactory(profile_image_url=None)
        self.course_run.staff.add(staff)

        setattr(staff, field, None)
        staff.save()
        self.assertFalse(self.course_run.has_valid_staff)

    def test_is_valid_micromasters(self):
        """ Verify that property returns bool if both fields have value. """
        self.assertTrue(self.course_run.is_valid_micromasters)

        self.course_run.is_micromasters = True
        self.course_run.micromasters_name = 'test'
        self.course_run.save()
        self.assertTrue(self.course_run.is_valid_micromasters)

        self.course_run.micromasters_name = None
        self.course_run.save()
        self.assertFalse(self.course_run.is_valid_micromasters)

    def test_is_professional_certificate(self):
        """ Verify that property returns bool if both fields have value. """
        self.assertTrue(self.course_run.is_valid_professional_certificate)

        self.course_run.is_professional_certificate = True
        self.course_run.professional_certificate_name = 'test'
        self.course_run.save()
        self.assertTrue(self.course_run.is_valid_professional_certificate)

        self.course_run.professional_certificate_name = None
        self.course_run.save()
        self.assertFalse(self.course_run.is_valid_professional_certificate)

    def test_is_valid_xseries(self):
        """ Verify that property returns bool if both fields have value. """
        self.assertTrue(self.course_run.is_valid_xseries)

        self.course_run.is_xseries = True
        self.course_run.xseries_name = 'test'
        self.course_run.save()
        self.assertTrue(self.course_run.is_valid_xseries)

        self.course_run.xseries_name = None
        self.course_run.save()
        self.assertFalse(self.course_run.is_valid_xseries)

    def test_has_valid_seats(self):
        """ Verify that property returns True if seats are valid. """
        factories.SeatFactory(course_run=self.course_run, type=Seat.AUDIT, price=0)
        invalid_seat = factories.SeatFactory(course_run=self.course_run, type=Seat.VERIFIED, price=0)
        self.assertFalse(self.course_run.has_valid_seats)

        invalid_seat.price = 200
        invalid_seat.save()

        self.assertTrue(self.course_run.has_valid_seats)

        credit_seat = factories.SeatFactory(course_run=self.course_run, type=Seat.CREDIT, price=0, credit_price=0)
        self.assertFalse(self.course_run.has_valid_seats)

        credit_seat.price = 200
        credit_seat.credit_price = 200
        credit_seat.save()

        self.assertTrue(self.course_run.has_valid_seats)


class CourseTests(TestCase):
    """ Tests for the publisher `Course` model. """

    def setUp(self):
        super(CourseTests, self).setUp()
        self.course = factories.CourseFactory()
        self.course2 = factories.CourseFactory()

        self.user1 = UserFactory()
        self.user2 = UserFactory()
        self.user3 = UserFactory()

        self.org_extension_1 = factories.OrganizationExtensionFactory()
        self.org_extension_2 = factories.OrganizationExtensionFactory()

        self.user1.groups.add(self.org_extension_1.group)
        self.user2.groups.add(self.org_extension_2.group)

        self.course.organizations.add(self.org_extension_1.organization)
        self.course2.organizations.add(self.org_extension_2.organization)

        # add user in course-user-role table
        factories.CourseUserRoleFactory(
            course=self.course, role=PublisherUserRole.ProjectCoordinator, user=self.user1
        )

        factories.CourseUserRoleFactory(
            course=self.course, role=PublisherUserRole.MarketingReviewer, user=self.user2
        )

        factories.CourseUserRoleFactory(
            course=self.course, role=PublisherUserRole.Publisher, user=self.user3
        )

    def test_str(self):
        """ Verify casting an instance to a string returns a string containing the course title. """
        self.assertEqual(str(self.course), self.course.title)

    def test_post_back_url(self):
        self.assertEqual(
            self.course.post_back_url,
            reverse('publisher:publisher_courses_edit', kwargs={'pk': self.course.id})
        )

    def test_assign_permission_organization_extension(self):
        """ Verify that permission can be assigned using the organization extension. """
        self.assert_user_cannot_view_course(self.user1, self.course, OrganizationExtension.VIEW_COURSE)
        self.assert_user_cannot_view_course(self.user2, self.course2, OrganizationExtension.VIEW_COURSE)

        self.course.organizations.add(self.org_extension_1.organization)
        self.course2.organizations.add(self.org_extension_2.organization)

        assign_perm(OrganizationExtension.VIEW_COURSE, self.org_extension_1.group, self.org_extension_1)
        assign_perm(OrganizationExtension.VIEW_COURSE, self.org_extension_2.group, self.org_extension_2)

        self.assert_user_can_view_course(self.user1, self.course, OrganizationExtension.VIEW_COURSE)
        self.assert_user_can_view_course(self.user2, self.course2, OrganizationExtension.VIEW_COURSE)

        self.assert_user_cannot_view_course(self.user1, self.course2, OrganizationExtension.VIEW_COURSE)
        self.assert_user_cannot_view_course(self.user2, self.course, OrganizationExtension.VIEW_COURSE)

        self.assertEqual(self.course.organizations.first().organization_extension.group, self.org_extension_1.group)
        self.assertEqual(self.course2.organizations.first().organization_extension.group, self.org_extension_2.group)

    def assert_user_cannot_view_course(self, user, course, permission):
        """ Asserts the user can NOT view the course. """
        self.assertFalse(check_course_organization_permission(user, course, permission))

    def assert_user_can_view_course(self, user, course, permission):
        """ Asserts the user can view the course. """
        self.assertTrue(check_course_organization_permission(user, course, permission))

    def test_get_course_users_emails(self):
        """ Verify the method returns the email addresses of users who are
        permitted to access the course AND have not disabled email notifications.
        """
        self.assertListEqual(
            self.course.get_course_users_emails(),
            [self.user1.email, self.user2.email, self.user3.email]
        )

        # The email addresses of users who have disabled email notifications should NOT be returned.
        factories.UserAttributeFactory(user=self.user1, enable_email_notification=False)
        self.assertListEqual(self.course.get_course_users_emails(), [self.user2.email, self.user3.email])

    def test_keywords_data(self):
        """ Verify that the property returns the keywords as comma separated string. """
        self.assertFalse(self.course.keywords_data)
        self.course.keywords.add('abc')
        self.assertEqual(self.course.keywords_data, 'abc')

        self.course.keywords.add('def')
        self.assertIn('abc', self.course.keywords_data)
        self.assertIn('def', self.course.keywords_data)

    def test_project_coordinator(self):
        """ Verify that the project_coordinator property returns user if exist. """
        self.assertIsNone(self.course2.project_coordinator)

        factories.CourseUserRoleFactory(
            course=self.course2, user=self.user1, role=PublisherUserRole.ProjectCoordinator
        )

        self.assertEqual(self.user1, self.course2.project_coordinator)

    def test_assign_roles(self):
        """
        Verify that method `assign_organization_role' assign course-user-roles except
        CourseTeam role for the organization against a course.
        """
        self.assertFalse(self.course2.course_user_roles.all())

        # create default roles for organization
        factories.OrganizationUserRoleFactory(
            role=PublisherUserRole.ProjectCoordinator, organization=self.org_extension_2.organization
        )
        factories.OrganizationUserRoleFactory(
            role=PublisherUserRole.MarketingReviewer, organization=self.org_extension_2.organization
        )

        factories.OrganizationUserRoleFactory(
            role=PublisherUserRole.CourseTeam, organization=self.org_extension_2.organization
        )

        self.course2.assign_organization_role(self.org_extension_2.organization)
        self.assertEqual(len(self.course2.course_user_roles.all()), 2)

        self.assertNotIn(PublisherUserRole.CourseTeam, self.course2.course_user_roles.all())

    def test_assign_roles_without_default_roles(self):
        """
        Verify that method `assign_organization_role' works fine even if no
        default roles exists.
        """
        self.course2.assign_organization_role(self.org_extension_2.organization)
        self.assertFalse(self.course2.course_user_roles.all())

    def test_course_runs(self):
        """ Verify that property returns queryset of course runs. """
        self.assertEqual(self.course.course_runs.count(), 0)

        factories.CourseRunFactory(course=self.course)

        self.assertEqual(self.course.course_runs.count(), 1)

    def test_course_team_admin(self):
        """ Verify that the course_team_admin property returns user if exist. """
        self.assertIsNone(self.course2.course_team_admin)

        factories.CourseUserRoleFactory(
            course=self.course2, user=self.user1, role=PublisherUserRole.CourseTeam
        )

        self.assertEqual(self.user1, self.course2.course_team_admin)

    def test_partner(self):
        """ Verify that the partner property returns organization partner if exist. """
        self.assertEqual(self.course.partner, self.org_extension_1.organization.partner)

    def test_marketing_reviewer(self):
        """ Verify that the marketing_reviewer property returns user if exist. """
        self.assertIsNone(self.course2.marketing_reviewer)

        factories.CourseUserRoleFactory(
            course=self.course2, user=self.user1, role=PublisherUserRole.MarketingReviewer
        )

        self.assertEqual(self.user1, self.course2.marketing_reviewer)

    def test_publisher(self):
        """ Verify that the publisher property returns user if exist. """
        self.assertIsNone(self.course2.publisher)

        factories.CourseUserRoleFactory(
            course=self.course2, user=self.user1, role=PublisherUserRole.Publisher
        )

        self.assertEqual(self.user1, self.course2.publisher)

    def test_course_image_url(self):
        """ Verify that the property returns the course image url. """
        self.assertIsNone(self.course.course_image_url)

        # Create a published course-run with card_image_url.
        course_run = factories.CourseRunFactory(course=self.course)
        factories.CourseRunStateFactory(course_run=course_run, name=CourseRunStateChoices.Published)
        course_run.card_image_url = 'http://example.com/test.jpg'
        course_run.save()

        # Verify that property returns card_image_url of course-run.
        self.assertEqual(self.course.course_image_url, course_run.card_image_url)

        # Create a course image.
        self.course.image = make_image_file('test_banner1.jpg')
        self.course.save()

        # Verify that property returns course image field url.
        self.assertEqual(self.course.course_image_url, self.course.image.url)

    def test_short_description_override(self):
        """ Verify that the property returns the short_description. """
        self.assertEqual(self.course.short_description, self.course.course_short_description)

        course_run = factories.CourseRunFactory(course=self.course)
        factories.CourseRunStateFactory(course_run=course_run, name=CourseRunStateChoices.Published)
        self.assertEqual(self.course.course_short_description, course_run.short_description_override)

    def test_full_description_override(self):
        """ Verify that the property returns the full_description. """
        self.assertEqual(self.course.full_description, self.course.course_full_description)

        course_run = factories.CourseRunFactory(course=self.course)
        factories.CourseRunStateFactory(course_run=course_run, name=CourseRunStateChoices.Published)
        self.assertEqual(self.course.course_full_description, course_run.full_description_override)

    def test_title_override(self):
        """ Verify that the property returns the title. """
        self.assertEqual(self.course.title, self.course.course_title)

        course_run = factories.CourseRunFactory(course=self.course)
        factories.CourseRunStateFactory(course_run=course_run, name=CourseRunStateChoices.Published)
        self.assertEqual(self.course.course_title, course_run.title_override)


class SeatTests(TestCase):
    """ Tests for the publisher `Seat` model. """

    def setUp(self):
        super(SeatTests, self).setUp()
        self.seat = factories.SeatFactory()

    def test_str(self):
        """ Verify casting an instance to a string returns a string containing the course title and seat type. """
        self.assertEqual(
            str(self.seat),
            '{course}: {type}'.format(
                course=self.seat.course_run.course.title, type=self.seat.type
            )
        )


class UserAttributeTests(TestCase):
    """ Tests for the publisher `UserAttribute` model. """

    def setUp(self):
        super(UserAttributeTests, self).setUp()
        self.user_attr = factories.UserAttributeFactory()

    def test_str(self):
        """ Verify casting an instance to a string returns a string containing the user name and
        current enable status. """
        self.assertEqual(
            str(self.user_attr),
            '{user}: {enable_email_notification}'.format(
                user=self.user_attr.user,
                enable_email_notification=self.user_attr.enable_email_notification
            )
        )


class OrganizationUserRoleTests(TestCase):
    """Tests of the OrganizationUserRole model."""

    def setUp(self):
        super(OrganizationUserRoleTests, self).setUp()
        self.org_user_role = factories.OrganizationUserRoleFactory(role=PublisherUserRole.ProjectCoordinator)

    def test_str(self):
        """Verify that a OrganizationUserRole is properly converted to a str."""
        self.assertEqual(
            str(self.org_user_role), '{organization}: {user}: {role}'.format(
                organization=self.org_user_role.organization,
                user=self.org_user_role.user,
                role=self.org_user_role.role
            )
        )

    def test_unique_constraint(self):
        """ Verify a user cannot have multiple rows for the same organization-role combination. """
        with self.assertRaises(IntegrityError):
            OrganizationUserRole.objects.create(
                user=self.org_user_role.user,
                organization=self.org_user_role.organization,
                role=self.org_user_role.role
            )


class CourseUserRoleTests(TestCase):
    """Tests of the CourseUserRole model."""

    def setUp(self):
        super(CourseUserRoleTests, self).setUp()
        self.course_user_role = factories.CourseUserRoleFactory(role=PublisherUserRole.ProjectCoordinator)
        self.course = factories.CourseFactory()
        self.user = UserFactory()
        self.marketing_reviewer_role = PublisherUserRole.MarketingReviewer

    def test_str(self):
        """Verify that a CourseUserRole is properly converted to a str."""
        expected_str = '{course}: {user}: {role}'.format(
            course=self.course_user_role.course, user=self.course_user_role.user, role=self.course_user_role.role
        )
        self.assertEqual(str(self.course_user_role), expected_str)

    def test_unique_constraint(self):
        """ Verify a user cannot have multiple rows for the same course-role combination."""
        with self.assertRaises(IntegrityError):
            CourseUserRole.objects.create(
                course=self.course_user_role.course, user=self.course_user_role.user, role=self.course_user_role.role
            )

    def test_add_course_roles(self):
        """
        Verify that method `add_course_roles` created the course user role.
        """
        course_role, created = CourseUserRole.add_course_roles(
            self.course, self.marketing_reviewer_role, self.user
        )
        self.assertTrue(created)
        self.assertEqual(course_role.course, self.course)
        self.assertEqual(course_role.user, self.user)
        self.assertEqual(course_role.role, self.marketing_reviewer_role)

    def test_add_course_roles_with_existing_record(self):
        """
        Verify that method `add_course_roles` does not create the duplicate
        course user role.
        """
        __, created = CourseUserRole.add_course_roles(
            self.course, self.marketing_reviewer_role, self.user
        )
        self.assertTrue(created)
        __, created = CourseUserRole.add_course_roles(
            self.course, self.marketing_reviewer_role, self.user
        )
        self.assertFalse(created)


class GroupOrganizationTests(TestCase):
    """Tests of the GroupOrganization model."""

    def setUp(self):
        super(GroupOrganizationTests, self).setUp()
        self.organization_extension = factories.OrganizationExtensionFactory()
        self.group_2 = factories.GroupFactory()

    def test_str(self):
        """Verify that a GroupOrganization is properly converted to a str."""
        expected_str = '{organization}: {group}'.format(
            organization=self.organization_extension.organization, group=self.organization_extension.group
        )
        self.assertEqual(str(self.organization_extension), expected_str)

    def test_one_to_one_constraint(self):
        """ Verify that same group or organization have only one record."""

        with self.assertRaises(IntegrityError):
            OrganizationExtension.objects.create(
                group=self.group_2,
                organization=self.organization_extension.organization
            )


@ddt.ddt
class CourseStateTests(TestCase):
    """ Tests for the publisher `CourseState` model. """

    @classmethod
    def setUpClass(cls):
        super(CourseStateTests, cls).setUpClass()
        cls.course_state = factories.CourseStateFactory(name=CourseStateChoices.Draft)
        cls.user = UserFactory()
        factories.CourseUserRoleFactory(
            course=cls.course_state.course, role=PublisherUserRole.CourseTeam, user=cls.user
        )

    def setUp(self):
        super(CourseStateTests, self).setUp()

        self.course = self.course_state.course
        self.course.image = make_image_file('test_banner.jpg')
        self.course.save()

        self.course.organizations.add(factories.OrganizationExtensionFactory().organization)

    def test_str(self):
        """
        Verify casting an instance to a string returns a string containing the current state display name.
        """
        self.assertEqual(str(self.course_state), self.course_state.get_name_display())

    @ddt.data(
        CourseStateChoices.Review,
        CourseStateChoices.Approved,
        CourseStateChoices.Draft
    )
    def test_change_state(self, state):
        """
        Verify that we can change course state according to workflow.
        """
        self.assertNotEqual(self.course_state.name, state)

        self.course_state.change_state(state=state, user=self.user)

        self.assertEqual(self.course_state.name, state)

    def test_review_with_condition_failed(self):
        """
        Verify that user cannot change state to `Review` if `can_send_for_review` failed.
        """
        self.course.image = None

        self.assertEqual(self.course_state.name, CourseStateChoices.Draft)

        with self.assertRaises(TransitionNotAllowed):
            self.course_state.change_state(state=CourseStateChoices.Review, user=self.user)

    def test_can_send_for_review(self):
        """
        Verify `can_send_for_review` return False if minimum required fields are empty or None.
        """
        self.assertTrue(self.course_state.can_send_for_review())

        self.course.image = None

        self.assertFalse(self.course_state.can_send_for_review())

    @ddt.data(
        PublisherUserRole.MarketingReviewer,
        PublisherUserRole.CourseTeam,
    )
    def test_change_owner_role(self, role):
        """
        Verify that method change_owner_role updates the role.
        """
        self.course_state.change_owner_role(role)
        self.assertEqual(self.course_state.owner_role, role)

    def _assert_course_run_status(self, actual_status, expected_status_text, expected_date):
        """
        Assert course statuses.
        """
        expected_status = {'status_text': expected_status_text, 'date': expected_date}
        self.assertEqual(actual_status, expected_status)

    def _change_state_and_owner(self, course_state):
        """
        Change course state to review and ownership to marketing.
        """
        course_state.name = CourseStateChoices.Review
        course_state.change_owner_role(PublisherUserRole.MarketingReviewer)

    def test_course_team_status(self):
        """
        Verify that course_team_status returns right statuses.
        """
        course_state = factories.CourseStateFactory(owner_role=PublisherUserRole.CourseTeam)
        self._assert_course_run_status(
            course_state.course_team_status, 'In Draft since', course_state.owner_role_modified
        )

        self._change_state_and_owner(course_state)
        self._assert_course_run_status(
            course_state.course_team_status, 'Submitted on', course_state.owner_role_modified
        )

        course_state.marketing_reviewed = True
        course_state.change_owner_role(PublisherUserRole.CourseTeam)
        self._assert_course_run_status(
            course_state.course_team_status, 'In Review since', course_state.owner_role_modified
        )

        course_state.approved()
        course_state.save()
        self._assert_course_run_status(
            course_state.course_team_status, 'Reviewed on', course_state.owner_role_modified
        )

    def test_internal_user_status(self):
        """
        Verify that internal_user_status returns right statuses.
        """
        course_state = factories.CourseStateFactory(owner_role=PublisherUserRole.CourseTeam)
        self._assert_course_run_status(course_state.internal_user_status, 'n/a', '')

        self._change_state_and_owner(course_state)
        self._assert_course_run_status(
            course_state.internal_user_status, 'In Review since', course_state.owner_role_modified
        )

        course_state.marketing_reviewed = True
        course_state.change_owner_role(PublisherUserRole.CourseTeam)
        self._assert_course_run_status(
            course_state.internal_user_status, 'Reviewed on', course_state.owner_role_modified
        )


@ddt.ddt
class CourseRunStateTests(TestCase):
    """ Tests for the publisher `CourseRunState` model. """

    @classmethod
    def setUpClass(cls):
        super(CourseRunStateTests, cls).setUpClass()
        cls.seat = factories.SeatFactory(type=Seat.VERIFIED, price=100)
        cls.course_run_state = factories.CourseRunStateFactory(
            course_run=cls.seat.course_run, name=CourseRunStateChoices.Draft
        )
        cls.course_run = cls.course_run_state.course_run
        cls.course = cls.course_run.course
        cls.user = UserFactory()

        factories.CourseStateFactory(
            name=CourseStateChoices.Approved, course=cls.course
        )
        factories.CourseUserRoleFactory(
            course=cls.course_run.course, role=PublisherUserRole.CourseTeam, user=cls.user
        )
        factories.CourseUserRoleFactory(
            course=cls.course_run.course, role=PublisherUserRole.MarketingReviewer, user=UserFactory()
        )

    def setUp(self):
        super(CourseRunStateTests, self).setUp()

        language_tag = LanguageTag(code='te-st', name='Test Language')
        language_tag.save()
        self.course_run.transcript_languages.add(language_tag)
        self.course_run.language = language_tag
        self.course_run.is_micromasters = True
        self.course_run.micromasters_name = 'test'
        self.course_run.lms_course_id = 'course-v1:edX+DemoX+Demo_Course'
        self.course_run.save()
        self.course.course_state.name = CourseStateChoices.Approved
        self.course.save()
        self.course_run.staff.add(PersonFactory())
        self.course_run_state.preview_accepted = False
        self.course_run_state.save()
        self.assertTrue(self.course_run_state.can_send_for_review())

    def test_str(self):
        """
        Verify casting an instance to a string returns a string containing the current state display name.
        """
        self.assertEqual(str(self.course_run_state), self.course_run_state.get_name_display())

    @ddt.data(
        CourseRunStateChoices.Review,
        CourseRunStateChoices.Approved,
        CourseRunStateChoices.Published,
        CourseRunStateChoices.Draft
    )
    def test_change_state(self, state):
        """
        Verify that we can change course-run state according to workflow.
        """
        self.assertNotEqual(self.course_run_state.name, state)
        self.course_run_state.change_state(state=state, user=self.user)
        self.assertEqual(self.course_run_state.name, state)

    def test_with_invalid_parent_course_state(self):
        """
        Verify that method return False if parent course is not approved.
        """
        self.course.course_state.name = CourseStateChoices.Review
        self.course.save()
        self.assertFalse(self.course_run_state.can_send_for_review())

    def test_can_send_for_review_with_invalid_program_type(self):
        """
        Verify that method return False if program type is invalid.
        """
        self.course_run.micromasters_name = None
        self.course_run.save()
        self.assertFalse(self.course_run_state.can_send_for_review())

    def test_can_send_for_review_with_invalid_seat(self):
        """
        Verify that method return False if data is missing.
        """
        # seat type is verified but its price is 0
        self.seat.price = 0
        self.seat.save()
        self.assertFalse(self.course_run_state.can_send_for_review())

    def test_can_send_for_review_with_no_seat(self):
        """
        Verify that method return False if data is missing.
        """
        self.course_run.seats.all().first().delete()
        self.assertFalse(self.course_run_state.can_send_for_review())

    def test_can_send_for_review_without_language(self):
        """
        Verify that method return False if data is missing.
        """
        self.course_run.language = None
        self.course_run.save()
        self.assertFalse(self.course_run_state.can_send_for_review())

    def test_can_send_for_review_without_transcript_language(self):
        """
        Verify that method return False if data is missing.
        """
        self.course_run.transcript_languages = []
        self.course_run.save()
        self.assertFalse(self.course_run_state.can_send_for_review())

    def test_preview_accepted(self):
        """
        Verify that property is_preview_accepted return Boolean.
        """
        self.assertFalse(self.course_run_state.is_preview_accepted)
        self.course_run_state.preview_accepted = True
        self.course_run_state.save()
        self.assertTrue(self.course_run_state.is_preview_accepted)

    @ddt.data(
        PublisherUserRole.Publisher,
        PublisherUserRole.CourseTeam,
    )
    def test_change_owner_role(self, role):
        """
        Verify that method change_owner_role updates the role.
        """
        self.course_run_state.change_owner_role(role)
        self.assertEqual(self.course_run_state.owner_role, role)

    def test_is_approved(self):
        """
        Verify that method return is_approved status.
        """
        self.assertFalse(self.course_run_state.is_approved)
        self.course_run_state.name = CourseRunStateChoices.Approved
        self.course_run_state.save()
        self.assertTrue(self.course_run_state.is_approved)

    def test_is_ready_to_publish(self):
        """
        Verify that method return is_ready_to_publish status.
        """
        self.assertFalse(self.course_run_state.is_ready_to_publish)
        self.course_run_state.name = CourseRunStateChoices.Approved
        self.course_run_state.preview_accepted = True
        self.course_run_state.save()
        self.assertTrue(self.course_run_state.is_ready_to_publish)

    def test_is_published(self):
        """
        Verify that method return is_published status.
        """
        self.assertFalse(self.course_run_state.is_published)
        self.course_run_state.name = CourseRunStateChoices.Published
        self.course_run_state.save()
        self.assertTrue(self.course_run_state.is_published)

    def test_is_draft(self):
        """
        Verify that method return is_draft status.
        """
        self.assertFalse(self.course_run_state.is_draft)
        self.course_run_state.name = CourseRunStateChoices.Draft
        self.course_run_state.save()
        self.assertTrue(self.course_run_state.is_draft)

    def test_is_in_review(self):
        """
        Verify that method return is_in_review status.
        """
        self.assertFalse(self.course_run_state.is_in_review)
        self.course_run_state.name = CourseRunStateChoices.Review
        self.course_run_state.save()
        self.assertTrue(self.course_run_state.is_in_review)
