# pylint: disable=no-member
import json
import random
from datetime import datetime, timedelta
from unittest import skip

import ddt
import factory
import mock
from bs4 import BeautifulSoup
from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.sites.models import Site
from django.core import mail
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError
from django.forms import model_to_dict
from django.http import HttpRequest
from django.test import TestCase
from django.urls import reverse
from guardian.shortcuts import assign_perm
from opaque_keys.edx.keys import CourseKey
from pytz import timezone
from testfixtures import LogCapture
from waffle.testutils import override_switch

from course_discovery.apps.api.tests.mixins import SiteMixin
from course_discovery.apps.core.models import Currency, User
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.core.tests.helpers import make_image_file
from course_discovery.apps.course_metadata.models import ProgramType as DiscoveryProgramType
from course_discovery.apps.course_metadata.tests.factories import (
    CourseFactory, CourseRunFactory, CurriculumCourseMembershipFactory, CurriculumFactory, OrganizationFactory,
    PersonFactory, ProgramFactory, SeatFactory, SeatTypeFactory, SubjectFactory
)
from course_discovery.apps.ietf_language_tags.models import LanguageTag
from course_discovery.apps.publisher.choices import (
    CourseRunStateChoices, CourseStateChoices, InternalUserRole, PublisherUserRole
)
from course_discovery.apps.publisher.constants import (
    ADMIN_GROUP_NAME, INTERNAL_USER_GROUP_NAME, PROJECT_COORDINATOR_GROUP_NAME, REVIEWER_GROUP_NAME
)
from course_discovery.apps.publisher.forms import CourseEntitlementForm
from course_discovery.apps.publisher.models import (
    Course, CourseEntitlement, CourseRun, CourseRunState, CourseState, OrganizationExtension, Seat
)
from course_discovery.apps.publisher.tests import factories
from course_discovery.apps.publisher.tests.utils import create_non_staff_user_and_login
from course_discovery.apps.publisher.utils import is_email_notification_enabled
from course_discovery.apps.publisher.views import (
    COURSE_ROLES, COURSES_ALLOWED_PAGE_SIZES, CourseRunDetailView, CreateCourseRunView, get_course_role_widgets_data
)
from course_discovery.apps.publisher.views import logger as publisher_views_logger
from course_discovery.apps.publisher.wrappers import CourseRunWrapper
from course_discovery.apps.publisher_comments.models import CommentTypeChoices
from course_discovery.apps.publisher_comments.tests.factories import CommentFactory


@ddt.ddt
class CreateCourseViewTests(SiteMixin, TestCase):
    """ Tests for the publisher `CreateCourseView`. """

    def setUp(self):
        super(CreateCourseViewTests, self).setUp()
        self.user = UserFactory()
        # add user to internal group
        self.internal_user_group = Group.objects.get(name=INTERNAL_USER_GROUP_NAME)
        self.user.groups.add(self.internal_user_group)

        # add user to external group e.g. a course team group
        self.organization_extension = factories.OrganizationExtensionFactory()
        self.group = self.organization_extension.group
        self.user.groups.add(self.group)

        self.course = factories.CourseFactory(organizations=[self.organization_extension.organization])

        self.client.login(username=self.user.username, password=USER_PASSWORD)

        # creating default organizations roles
        factories.OrganizationUserRoleFactory(
            role=PublisherUserRole.ProjectCoordinator, organization=self.organization_extension.organization
        )
        factories.OrganizationUserRoleFactory(
            role=PublisherUserRole.MarketingReviewer, organization=self.organization_extension.organization
        )

    def test_course_form_without_login(self):
        """ Verify that user can't access new course form page when not logged in. """
        self.client.logout()
        response = self.client.get(reverse('publisher:publisher_courses_new'))

        self.assertRedirects(
            response,
            expected_url='{url}?next={next}'.format(
                url=reverse('login'),
                next=reverse('publisher:publisher_courses_new')
            ),
            status_code=302,
            target_status_code=302
        )

    def test_page_without_publisher_group_access(self):
        """
        Verify that user can't access new course form page if user is not the part of any group.
        """
        self.client.logout()
        self.client.login(username=UserFactory().username, password=USER_PASSWORD)
        response = self.client.get(reverse('publisher:publisher_courses_new'))
        self.assertContains(
            response, "Must be Publisher user to perform this action.", status_code=403
        )

    def test_create_course_with_errors(self):
        """
        Verify that without providing required data course cannot be created.
        """
        course_dict = model_to_dict(self.course)
        course_dict['number'] = ''
        course_dict['image'] = ''
        course_dict['lms_course_id'] = ''
        response = self.client.post(reverse('publisher:publisher_courses_new'), course_dict)
        self.assertEqual(response.status_code, 400)

    @ddt.data(
        make_image_file('test_cover00.jpg', width=2120, height=1192),
        make_image_file('test_cover01.jpg', width=1134, height=675),
        make_image_file('test_cover02.jpg', width=378, height=225),
    )
    def test_create_course_valid_image(self, image):
        """
        Verify a new course with valid image of acceptable image sizes can be saved properly
        """
        data = {'title': 'Test valid', 'number': 'testX453', 'image': image, 'url_slug': ''}
        course_dict = self._post_data(data, self.course)
        response = self.client.post(reverse('publisher:publisher_courses_new'), course_dict)
        course = Course.objects.get(number=course_dict['number'])
        self.assertRedirects(
            response,
            expected_url=reverse('publisher:publisher_course_detail', kwargs={'pk': course.id}),
            status_code=302,
            target_status_code=200
        )
        self.assertEqual(course.number, data['number'])
        self._assert_image(course)

    @ddt.data(
        make_image_file('test_banner00.jpg', width=2120, height=1191),
        make_image_file('test_banner01.jpg', width=2120, height=1193),
        make_image_file('test_banner02.jpg', width=2119, height=1192),
        make_image_file('test_banner03.jpg', width=2121, height=1192),
        make_image_file('test_banner04.jpg', width=2121, height=1191),
        make_image_file('test_cover01.jpg', width=1600, height=1100),
        make_image_file('test_cover01.jpg', width=300, height=220),
    )
    def test_create_course_invalid_image(self, image):
        """
        Verify that a new course with an invalid image shows the proper error.
        """
        image_error = [
            'Invalid image size. The recommended image size is 1134 X 675 pixels. ' +
            'Older courses also support image sizes of ' +
            '2120 X 1192 px or 378 X 225 px.',
        ]
        self.user.groups.add(Group.objects.get(name=ADMIN_GROUP_NAME))
        self._assert_records(1)
        course_dict = self._post_data({'image': image}, self.course)
        response = self.client.post(reverse('publisher:publisher_courses_new'), course_dict, files=image)
        self.assertEqual(response.context['course_form'].errors['image'], image_error)
        self._assert_records(1)

    def test_create_with_fail_transaction(self):
        """
        Verify that in case of any error transactions rollback and no object is created in db.
        """
        self._assert_records(1)
        data = {'number': 'course_2', 'image': make_image_file('test_banner.jpg')}
        course_dict = self._post_data(data, self.course)
        with mock.patch.object(Course, "save") as mock_method:
            mock_method.side_effect = IntegrityError
            response = self.client.post(reverse('publisher:publisher_courses_new'), course_dict, files=data['image'])

        self.assertEqual(response.status_code, 400)
        self._assert_records(1)

    def test_create_with_exception(self):
        """
        Verify that in case of any error transactions rollback and no object is created in db.
        """
        self._assert_records(1)
        data = {'number': 'course_2', 'image': make_image_file('test_banner.jpg')}
        course_dict = self._post_data(data, self.course)
        with mock.patch.object(Course, "save") as mock_method:
            mock_method.side_effect = Exception('test')
            response = self.client.post(reverse('publisher:publisher_courses_new'), course_dict, files=data['image'])

        self.assertEqual(response.status_code, 400)
        self.assertRaises(Exception)
        self._assert_records(1)

    def test_create_form_with_single_organization(self):
        """Verify that if there is only one organization then that organization will be shown as text. """
        response = self.client.get(reverse('publisher:publisher_courses_new'))
        self.assertContains(response, '<input id="id_organization" name="organization" type="hidden"')

    def test_create_form_with_multiple_organization(self):
        """
        Verify that a drop down of organization choices exisits if there are multiple organizations.
        """
        self.user.groups.remove(self.internal_user_group)
        organization_extension = factories.OrganizationExtensionFactory()
        self.user.groups.add(organization_extension.group)
        response = self.client.get(reverse('publisher:publisher_courses_new'))
        response_content = BeautifulSoup(response.content)

        organization_attribute = response_content.find(
            "select", {"id": "id_organization", "name": "organization", "class": "field-input"}
        )
        assert organization_attribute is not None

        new_organization_extension = factories.OrganizationExtensionFactory()
        response = self.client.get(reverse('publisher:publisher_courses_new'))

        # Verify that course team user cannot see newly created organization in options.
        self.assertNotContains(
            response,
            '<option value="{value}">{key}: {name}</option>'.format(
                value=new_organization_extension.organization.id,
                key=new_organization_extension.organization.key,
                name=new_organization_extension.organization.name
            )
        )

        self.user.groups.add(self.internal_user_group)
        response = self.client.get(reverse('publisher:publisher_courses_new'))

        # Verify that internal user can see newly created organization in options.
        self.assertContains(
            response,
            '<option value="{value}">{key}: {name}</option>'.format(
                value=new_organization_extension.organization.id,
                key=new_organization_extension.organization.key,
                name=new_organization_extension.organization.name
            )
        )

    def test_create_course_without_course_number(self):
        """
        Verify that without course number course cannot be created.
        """
        course_dict = self._post_data({'image': ''}, self.course)
        course_dict.pop('number')
        response = self.client.post(reverse('publisher:publisher_courses_new'), course_dict)
        self.assertEqual(response.status_code, 400)

    def test_page_with_pilot_switch_enable(self):
        """ Verify that about page information panel is not visible on new course page."""
        response = self.client.get(reverse('publisher:publisher_courses_new'))
        self.assertNotIn(
            '<div id="about-page" class="layout-full publisher-layout layout', response.content.decode('UTF-8')
        )

    def _post_data(self, data, course):
        """ Returns dict of data to posts to a course endpoint. """
        course_dict = model_to_dict(course)
        course_dict.update(**data)
        course_dict['team_admin'] = self.user.id
        course_dict['organization'] = self.organization_extension.organization.id
        course_dict.pop('id')

        return course_dict

    def _assert_image(self, course):
        """ Asserts image with proper prefixes and file sizes present on course images"""
        image_url_prefix = '{}media/publisher/courses/images'.format(settings.MEDIA_URL)
        self.assertIn(image_url_prefix, course.image.url)
        for size_key in course.image.field.variations:
            # Get different sizes specs from the model field
            # Then get the file path from the available files
            sized_file = getattr(course.image, size_key, None)
            self.assertIsNotNone(sized_file)
            self.assertIn(image_url_prefix, sized_file.url)

    def _assert_records(self, count):
        """ Asserts expected counts for Course"""
        self.assertEqual(Course.objects.all().count(), count)

    def test_create_course_with_add_run(self):
        """
        Verify that if add_new_run is checked user is redirected to
        create course run page instead course detail page.
        """
        data = {'title': 'Test2', 'number': 'testX234', 'image': '', 'add_new_run': True, 'url_slug': ''}
        course_dict = self._post_data(data, self.course)
        response = self.client.post(reverse('publisher:publisher_courses_new'), course_dict)

        course = Course.objects.get(number=course_dict['number'])

        self.assertRedirects(
            response,
            expected_url=reverse('publisher:publisher_course_runs_new', kwargs={'parent_course_id': course.id}),
            status_code=302,
            target_status_code=200
        )

    def _create_course_with_post(self, data=None):
        initial_data = {'title': 'Test Course', 'number': 'test1', 'image': '', 'url_slug': ''}
        if data:
            initial_data.update(**data)
        course_dict = self._post_data(initial_data, self.course)
        response = self.client.post(reverse('publisher:publisher_courses_new'), course_dict)
        self.assertRedirects(
            response,
            expected_url=reverse('publisher:publisher_course_detail', kwargs={'pk': Course.objects.first().id}),
            status_code=302,
            target_status_code=200
        )
        return Course.objects.get(number=course_dict['number'])

    @ddt.data(CourseEntitlementForm.VERIFIED_MODE, CourseEntitlementForm.PROFESSIONAL_MODE)
    def test_create_entitlement(self, mode):
        """
        Verify that we create an entitlement for appropriate types (happy path)
        """
        data = {'mode': mode, 'price': 50}
        course = self._create_course_with_post(data)

        self.assertEqual(1, CourseEntitlement.objects.all().count())
        self.assertEqual(1, course.entitlements.all().count())
        self.assertEqual(Course.ENTITLEMENT_VERSION, course.version)

        entitlement = course.entitlements.first()
        self.assertEqual(course, entitlement.course)
        self.assertEqual(mode, entitlement.mode)
        self.assertEqual(50, entitlement.price)

    @ddt.data(
        {},
        {'mode': CourseEntitlementForm.AUDIT_MODE, 'price': 0},
        {'mode': CourseEntitlementForm.CREDIT_MODE, 'price': 0}
    )
    def test_seat_version(self, entitlement_form_data):
        """
        Verify that when we create a course without a mode, or with a mode that doesn't support entitlements,
        we set version correctly
        """
        course = self._create_course_with_post(entitlement_form_data)
        self.assertEqual(0, CourseEntitlement.objects.all().count())
        self.assertEqual(Course.SEAT_VERSION, course.version)

    @ddt.data(0, -1, None)
    def test_invalid_entitlement_price(self, price):
        """
        Verify that we check price validity when making an entitlement
        """
        data = {'title': 'Test2', 'number': 'testX234', 'mode': CourseEntitlementForm.VERIFIED_MODE}
        if price is not None:
            data['price'] = price
        course_dict = self._post_data(data, self.course)
        response = self.client.post(reverse('publisher:publisher_courses_new'), course_dict)
        self.assertEqual(response.status_code, 400)


@ddt.ddt
class CreateCourseRunViewTests(SiteMixin, TestCase):
    """ Tests for the publisher `CreateCourseRunView`. """

    def setUp(self):
        super(CreateCourseRunViewTests, self).setUp()
        self.user = UserFactory()
        self.course_run = factories.CourseRunFactory()

        self.course = self.course_run.course
        self.course.version = Course.SEAT_VERSION
        self.course.save()

        factories.CourseStateFactory(course=self.course)
        factories.CourseUserRoleFactory.create(course=self.course, role=PublisherUserRole.CourseTeam, user=self.user)
        factories.CourseUserRoleFactory.create(course=self.course, role=PublisherUserRole.Publisher, user=UserFactory())
        factories.CourseUserRoleFactory.create(
            course=self.course, role=PublisherUserRole.ProjectCoordinator, user=UserFactory()
        )
        factories.CourseUserRoleFactory.create(
            course=self.course, role=PublisherUserRole.MarketingReviewer, user=UserFactory()
        )
        self.organization_extension = factories.OrganizationExtensionFactory(organization__partner=self.partner)
        self.course.organizations.add(self.organization_extension.organization)
        self.user.groups.add(self.organization_extension.group)

        self.course_run_dict = model_to_dict(self.course_run)
        self.course_run_dict.update({'is_self_paced': True})
        self._pop_valuse_from_dict(
            self.course_run_dict,
            ['end', 'priority', 'certificate_generation', 'id']
        )
        current_datetime = datetime.now(timezone('US/Central'))
        self.course_run_dict['start'] = (current_datetime + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
        self.course_run_dict['end'] = (current_datetime + timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S')
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.create_course_run_url_new = reverse(
            'publisher:publisher_course_runs_new',
            kwargs={'parent_course_id': self.course.id}
        )

    def _pop_valuse_from_dict(self, data_dict, key_list):
        for key in key_list:
            data_dict.pop(key)

    def test_courserun_form_with_login(self):
        """ Verify that user can access new course run form page when logged in. """
        response = self.client.get(self.create_course_run_url_new)

        self.assertEqual(response.status_code, 200)

    def test_courserun_form_without_login(self):
        """ Verify that user can't access new course run form page when not logged in. """
        self.client.logout()
        response = self.client.get(self.create_course_run_url_new)

        self.assertRedirects(
            response,
            expected_url='{url}?next={next}'.format(
                url=reverse('login'),
                next=self.create_course_run_url_new
            ),
            status_code=302,
            target_status_code=302
        )

        self.client.login(username=self.user.username, password=USER_PASSWORD)

        response = self.client.get(self.create_course_run_url_new)
        self.assertEqual(response.status_code, 200)

    def test_courserun_form_for_course_with_entitlements(self):
        """ Verify that the Seat fields are hidden for Courses that use entitlements. """
        self.course.version = Course.ENTITLEMENT_VERSION
        self.course.save()

        response = self.client.get(self.create_course_run_url_new)
        self.assertContains(response, '<div class="layout-full layout js-seat-form hidden">', status_code=200)

    def test_courserun_form_for_course_without_entitlements(self):
        """ Verify that the Seat fields are visible for Courses that do not use entitlements. """
        self.course.version = Course.SEAT_VERSION
        self.course.save()

        response = self.client.get(self.create_course_run_url_new)
        self.assertContains(response, '<div class="layout-full layout js-seat-form">', status_code=200)

    def test_create_course_run_without_permission(self):
        """
        Verify that a course run create page shows the proper error when non-publisher user tries to
        access it.
        """
        create_non_staff_user_and_login(self)
        response = self.client.get(self.create_course_run_url_new)
        self.assertContains(
            response, "Must be Publisher user to perform this action.", status_code=403
        )

    def test_create_course_run_and_seat_with_errors(self):
        """ Verify that without providing required data course run cannot be
        created.
        """
        post_data = self.course_run_dict
        post_data.update(factory.build(dict, FACTORY_CLASS=factories.SeatFactory))
        self._pop_valuse_from_dict(
            post_data, ['upgrade_deadline', 'start']
        )

        response = self.client.post(self.create_course_run_url_new, post_data)
        self.assertEqual(response.status_code, 400)

        with mock.patch('django.forms.models.BaseModelForm.is_valid') as mocked_is_valid:
            mocked_is_valid.return_value = True
            with LogCapture(publisher_views_logger.name) as log_capture:
                response = self.client.post(self.create_course_run_url_new, post_data)
                self.assertEqual(response.status_code, 400)
                log_capture.check(
                    (
                        publisher_views_logger.name,
                        'ERROR',
                        'Unable to create course run and seat for course [{}].'.format(self.course.id)
                    )
                )

    def test_create_course_run_and_seat(self):
        """ Verify that we can create a new course run with seat. """
        new_user = factories.UserFactory()
        new_user.groups.add(self.organization_extension.group)

        self.assertEqual(self.course.course_team_admin, self.user)

        new_price = 450
        post_data = self.course_run_dict
        seat = factories.SeatFactory(course_run=self.course_run, type=Seat.HONOR, price=0)
        post_data.update(**model_to_dict(seat))
        post_data.update(
            {
                'type': Seat.VERIFIED,
                'price': new_price
            }
        )
        self._pop_valuse_from_dict(post_data, ['id', 'course', 'course_run', 'lms_course_id'])
        assign_perm(
            OrganizationExtension.VIEW_COURSE_RUN, self.organization_extension.group, self.organization_extension
        )
        response = self.client.post(self.create_course_run_url_new, post_data)

        new_seat = Seat.objects.get(type=post_data['type'], price=post_data['price'])
        self.assertRedirects(
            response,
            expected_url=reverse('publisher:publisher_course_run_detail', kwargs={'pk': new_seat.course_run.id}),
            status_code=302,
            target_status_code=200
        )

        # Verify that new seat and new course run are unique
        self.assertNotEqual(new_seat.type, seat.type)
        self.assertEqual(new_seat.type, Seat.VERIFIED)
        self.assertNotEqual(new_seat.price, seat.price)
        self.assertEqual(new_seat.price, new_price)
        self.assertNotEqual(new_seat.course_run, self.course_run)

        # Verify that and email is sent for studio instance request to project coordinator.
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual([self.course.project_coordinator.email], mail.outbox[0].to)
        expected_subject = 'Studio URL requested: {title}'.format(title=self.course.title)
        self.assertEqual(str(mail.outbox[0].subject), expected_subject)

    def test_data_copy_over_on_create_course_run(self):
        """
        Test that new course run is populated with data from previous run of same course.
        """
        course_run_staff = PersonFactory()
        self.course_run.staff.add(course_run_staff)
        language_tag = LanguageTag(code='te-st', name='Test Language')
        language_tag.save()
        self.course_run.transcript_languages.add(language_tag)

        seat = factories.SeatFactory(course_run=self.course_run, type=Seat.AUDIT, price=0, credit_price=0)

        self.assertEqual(len(self.course.course_runs), 1)

        post_data = {'start': '2018-02-01 00:00:00', 'end': '2018-02-28 00:00:00', 'pacing_type': 'instructor_paced'}
        post_data.update(**model_to_dict(seat))
        response = self.client.post(self.create_course_run_url_new, post_data)

        self.assertEqual(len(self.course.course_runs), 2)

        new_run = self.course.course_runs.latest('created')

        assign_perm(
            OrganizationExtension.VIEW_COURSE_RUN, self.organization_extension.group, self.organization_extension
        )
        self.assertRedirects(
            response,
            expected_url=reverse('publisher:publisher_course_run_detail', kwargs={'pk': new_run.id}),
            status_code=302,
            target_status_code=200
        )

        fields_to_assert = [
            'title_override',
            'min_effort',
            'max_effort',
            'length',
            'notes',
            'language',
            'full_description_override',
            'short_description_override'
        ]

        for field in fields_to_assert:
            self.assertEqual(getattr(new_run, field), getattr(self.course_run, field))

        self.assertEqual(list(new_run.staff.all()), list(self.course_run.staff.all()))
        self.assertEqual(list(new_run.transcript_languages.all()), list(self.course_run.transcript_languages.all()))

    def test_seat_without_price(self):
        """ Verify that user cannot create a new course run without seat price. """
        new_user = factories.UserFactory()
        new_user.groups.add(self.organization_extension.group)

        self.assertEqual(self.course.course_team_admin, self.user)

        post_data = self.course_run_dict
        seat = factories.SeatFactory(course_run=self.course_run, type=Seat.HONOR, price=0)
        post_data.update(**model_to_dict(seat))
        post_data.update(
            {
                'type': Seat.VERIFIED,
                'price': 0
            }
        )
        self._pop_valuse_from_dict(post_data, ['id', 'course', 'course_run', 'lms_course_id'])
        assign_perm(
            OrganizationExtension.VIEW_COURSE_RUN, self.organization_extension.group, self.organization_extension
        )
        response = self.client.post(self.create_course_run_url_new, post_data)
        self.assertContains(response, 'Only audit seat can be without price.', status_code=400)

        post_data['price'] = 450

        response = self.client.post(self.create_course_run_url_new, post_data)
        new_seat = Seat.objects.get(type=post_data['type'], price=post_data['price'])
        self.assertRedirects(
            response,
            expected_url=reverse('publisher:publisher_course_run_detail', kwargs={'pk': new_seat.course_run.id}),
            status_code=302,
            target_status_code=200
        )

    def test_existing_run_and_seat_data_auto_populated(self):
        """
        Verify that existing course run and seat data auto populated on new course run form.

        Create a course run with a verified seat (for a verified and credit seat, audit seat
        is automatically created), then try to create a new run of the same course and verify
        the previous course run's seats are automatically populated.
        """
        verified_seat_price = 550.0
        latest_run = self.course.course_runs.latest('created')
        factories.SeatFactory(course_run=latest_run, type=Seat.VERIFIED, price=verified_seat_price)
        factories.SeatFactory(course_run=latest_run, type=Seat.AUDIT)

        # Verified seat should be preselected
        verified_seat = latest_run.seats.get(type=Seat.VERIFIED)
        response = self.client.get(self.create_course_run_url_new)
        response_content = BeautifulSoup(response.content)

        seat_type_attribute = response_content.find("option", {"value": verified_seat.type})
        price_attribute = response_content.find(
            "input", {"value": verified_seat.price, "id": "id_price", "step": "0.01", "type": "number"}
        )
        masters_block_attribute = response_content.find("div", {'id': "mastersTrackBlock"})

        # Verify that existing course run and seat values auto populated on form.
        self.assertIsNotNone(seat_type_attribute)
        self.assertIn('selected=""', str(seat_type_attribute))
        self.assertIsNotNone(price_attribute)
        self.assertIn(str(verified_seat_price), str(price_attribute))

        # Verify that masters track checkbox is hidden
        self.assertIsNotNone(masters_block_attribute)
        self.assertIn('hidden', str(masters_block_attribute))

    @ddt.data(True, False)
    def test_masters_course_mode_checkbox(self, last_run_masters_seat):
        """
        Verify that when we attempt to create a new course run, the master's course mode
        checkbox appears if the course is part of a master's program

        Also check that if the current canonical course run has a masters seat, the checkbox is
        checked by default and visa versa
        """
        verified_seat_price = 550.0
        latest_run = self.course.course_runs.latest('created')
        factories.SeatFactory(course_run=latest_run, type=Seat.VERIFIED, price=verified_seat_price)
        factories.SeatFactory(course_run=latest_run, type=Seat.AUDIT)
        self.course.number = 'Masters101'
        self.course.save()

        masters_program_type = DiscoveryProgramType.objects.get(slug='masters')
        discovery_program = ProgramFactory(type=masters_program_type)
        discovery_curriculum = CurriculumFactory(program=discovery_program)
        discovery_course = CourseFactory(partner=self.partner, key=self.course.key)
        CurriculumCourseMembershipFactory(
            course=discovery_course,
            curriculum=discovery_curriculum
        )
        if last_run_masters_seat:
            discovery_course.canonical_course_run = CourseRunFactory(course=discovery_course)
            discovery_course.save()
            masters_seat_type = SeatTypeFactory.masters()
            discovery_course.canonical_course_run.seats.add(SeatFactory(type=masters_seat_type))
            discovery_course.canonical_course_run.save()

        response = self.client.get(self.create_course_run_url_new)

        response_content = BeautifulSoup(response.content)
        masters_block_attribute = response_content.find("div", {'id': "mastersTrackBlock"})
        masters_track_checkbox = response_content.find("input", {'id': "id_masters_track"})

        # Verify that masters track checkbox is visible and correctly checked
        self.assertIsNotNone(masters_block_attribute)
        self.assertNotIn('hidden', str(masters_block_attribute))
        self.assertIsNotNone(masters_track_checkbox)
        # Verify that the box is checked if the canonical course run has a masters seat
        view = CreateCourseRunView()
        view.kwargs = {'parent_course_id': self.course.id}
        context_data = view.get_context_data()
        self.assertEqual(last_run_masters_seat, context_data['seat_form'].initial['masters_track'])

    def test_credit_type_without_price(self):
        """ Verify that without credit price course-run cannot be created with credit seat type. """
        post_data = self.course_run_dict
        seat = factories.SeatFactory(course_run=self.course_run, type=Seat.AUDIT, price=0, credit_price=0)
        post_data.update(**model_to_dict(seat))
        post_data.update(
            {
                'type': Seat.CREDIT,
                'price': 450
            }
        )
        self._pop_valuse_from_dict(post_data, ['id', 'course', 'course_run', 'lms_course_id'])
        assign_perm(
            OrganizationExtension.VIEW_COURSE_RUN, self.organization_extension.group, self.organization_extension
        )
        response = self.client.post(self.create_course_run_url_new, post_data)
        self.assertEqual(response.status_code, 400)

    def test_create_course_run_with_credit_seat(self):
        """ Verify that user can create a new course run with credit seat. """
        price = 450
        credit_price = 350
        post_data = self.course_run_dict
        seat = factories.SeatFactory(course_run=self.course_run, type=Seat.AUDIT, price=0, credit_price=0)
        post_data.update(**model_to_dict(seat))
        post_data.update(
            {
                'type': Seat.CREDIT,
                'price': price,
                'credit_price': credit_price
            }
        )
        self._pop_valuse_from_dict(post_data, ['id', 'course', 'course_run', 'lms_course_id'])
        assign_perm(
            OrganizationExtension.VIEW_COURSE_RUN, self.organization_extension.group, self.organization_extension
        )
        response = self.client.post(self.create_course_run_url_new, post_data)

        new_seat = Seat.objects.get(type=post_data['type'])
        self.assertRedirects(
            response,
            expected_url=reverse('publisher:publisher_course_run_detail', kwargs={'pk': new_seat.course_run.id}),
            status_code=302,
            target_status_code=200
        )

        # Verify that new seat and new course run are unique
        self.assertEqual(new_seat.type, Seat.CREDIT)
        self.assertEqual(new_seat.price, price)
        self.assertEqual(new_seat.credit_price, credit_price)

    def test_cannot_create_course_run_without_roles(self):
        """
        Verify that user can not create a new course run if the course user roles are not complete.
        """
        organization_extension = factories.OrganizationExtensionFactory()
        course = factories.CourseFactory(organizations=[organization_extension.organization])
        self.user.groups.add(organization_extension.group)
        create_course_run_url = reverse('publisher:publisher_course_runs_new', kwargs={'parent_course_id': course.id})
        course_user_roles = course.course_user_roles.filter(role__in=COURSE_ROLES)
        with LogCapture(publisher_views_logger.name) as log_capture:
            response = self.client.post(create_course_run_url, {})
            self.assertContains(response, 'Your organization does not have default roles', status_code=400)
            log_capture.check(
                (
                    publisher_views_logger.name,
                    'ERROR',
                    'Course [{}] is missing default course roles. Current roles [{}], required roles [{}]'.format(
                        course.id,
                        course_user_roles.count(),
                        len(COURSE_ROLES)
                    )
                )
            )

    @ddt.data(
        (CourseEntitlement.PROFESSIONAL, 1, [{'type': Seat.PROFESSIONAL, 'price': 1}]),
        (CourseEntitlement.VERIFIED, 1, [{'type': Seat.VERIFIED, 'price': 1}, {'type': Seat.AUDIT, 'price': 0}]),
    )
    @ddt.unpack
    def test_create_run_for_entitlement_course(self, entitlement_mode, entitlement_price, expected_seats):
        """
        Verify that when creating a run for a Course that uses entitlements, Seats are created from the
        entitlement data associated with the parent course.
        """
        self.course.version = Course.ENTITLEMENT_VERSION
        self.course.save()
        assign_perm(
            OrganizationExtension.VIEW_COURSE_RUN, self.organization_extension.group, self.organization_extension
        )

        self.course.entitlements.create(mode=entitlement_mode, price=entitlement_price)
        post_data = {'start': '2018-02-01 00:00:00', 'end': '2018-02-28 00:00:00', 'pacing_type': 'instructor_paced'}

        num_courseruns_before = self.course.course_runs.count()
        response = self.client.post(self.create_course_run_url_new, post_data)
        num_courseruns_after = self.course.course_runs.count()
        self.assertGreater(num_courseruns_after, num_courseruns_before)

        new_courserun = self.course.course_runs.latest('created')
        self.assertEqual(new_courserun.start_date_temporary.strftime('%Y-%m-%d %H:%M:%S'), post_data['start'])
        self.assertEqual(new_courserun.end_date_temporary.strftime('%Y-%m-%d %H:%M:%S'), post_data['end'])
        self.assertEqual(new_courserun.pacing_type_temporary, post_data['pacing_type'])

        self.assertRedirects(
            response,
            expected_url=reverse('publisher:publisher_course_run_detail', kwargs={'pk': new_courserun.id}),
            status_code=302,
            target_status_code=200
        )

        self.assertEqual(new_courserun.seats.count(), len(expected_seats))
        for expected_seat in expected_seats:
            actual_seat = new_courserun.seats.get(type=expected_seat['type'])
            self.assertEqual(expected_seat['type'], actual_seat.type)
            self.assertEqual(expected_seat['price'], actual_seat.price)

    def test_create_run_for_misconfigured_entitlement_course(self):
        """
        Verify that a user cannot create a new course run for a Course that has been configured to use entitlements
        but does not have exactly one entitlement.
        """
        self.course.version = Course.ENTITLEMENT_VERSION
        self.course.save()
        assign_perm(
            OrganizationExtension.VIEW_COURSE_RUN, self.organization_extension.group, self.organization_extension
        )
        post_data = {'start': '2018-02-01 00:00:00', 'end': '2018-02-28 00:00:00', 'pacing_type': 'instructor_paced'}

        self.assertEqual(self.course.entitlements.count(), 0)
        num_courseruns_before = self.course.course_runs.count()

        response = self.client.post(self.create_course_run_url_new, post_data)
        num_courseruns_after = self.course.course_runs.count()
        self.assertEqual(num_courseruns_before, num_courseruns_after)
        self.assertContains(response, 'The certificate configuration for this course is incorrect', status_code=400)

        self.course.entitlements.create(mode=CourseEntitlement.VERIFIED, price=1)
        self.course.entitlements.create(mode=CourseEntitlement.PROFESSIONAL, price=1)
        self.assertEqual(self.course.entitlements.count(), 2)

        response = self.client.post(self.create_course_run_url_new, post_data)
        num_courseruns_after = self.course.course_runs.count()
        self.assertEqual(num_courseruns_before, num_courseruns_after)
        self.assertContains(response, 'The certificate configuration for this course is incorrect', status_code=400)

    def test_create_run_for_non_usd_entitlement_course(self):
        """
        Verify that a user cannot create a new course run for a Course that has been configured to use entitlements
        with a currency other than USD.
        """
        self.course.version = Course.ENTITLEMENT_VERSION
        self.course.save()
        assign_perm(
            OrganizationExtension.VIEW_COURSE_RUN, self.organization_extension.group, self.organization_extension
        )
        post_data = {'start': '2018-02-01 00:00:00', 'end': '2018-02-28 00:00:00', 'pacing_type': 'instructor_paced'}
        self.course.entitlements.create(
            mode=CourseEntitlement.VERIFIED,
            price=100,
            currency=Currency.objects.get(code='JPY')
        )
        num_courseruns_before = self.course.course_runs.count()

        response = self.client.post(self.create_course_run_url_new, post_data)
        num_courseruns_after = self.course.course_runs.count()
        self.assertEqual(num_courseruns_before, num_courseruns_after)
        self.assertContains(response, 'The certificate configuration for this course is incorrect', status_code=400)

    def test_create_run_for_entitlement_course_with_seat_data_in_form(self):
        """
        Verify that a user cannot submit Seat data with the form when creating a new course run for a Course that has
        been configured to use entitlements.
        """
        self.course.version = Course.ENTITLEMENT_VERSION
        self.course.save()
        assign_perm(
            OrganizationExtension.VIEW_COURSE_RUN, self.organization_extension.group, self.organization_extension
        )
        post_data = {
            'start': '2018-02-01 00:00:00',
            'end': '2018-02-28 00:00:00',
            'pacing_type': 'instructor_paced',
            'type': Seat.VERIFIED,
            'price': 2
        }

        self.course.entitlements.create(mode=CourseEntitlement.PROFESSIONAL, price=1)
        num_courseruns_before = self.course.course_runs.count()
        response = self.client.post(self.create_course_run_url_new, post_data)
        num_courseruns_after = self.course.course_runs.count()
        self.assertEqual(num_courseruns_before, num_courseruns_after)
        self.assertContains(response, 'The page could not be updated.', status_code=400)


@ddt.ddt
class CourseRunDetailTests(SiteMixin, TestCase):
    """ Tests for the course-run detail view. """

    def setUp(self):
        super(CourseRunDetailTests, self).setUp()
        self.user = UserFactory()
        self.user.groups.add(Group.objects.get(name=ADMIN_GROUP_NAME))
        self.organization_extension = factories.OrganizationExtensionFactory()
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.course_run = factories.CourseRunFactory(course__organizations=[self.organization_extension.organization],
                                                     lms_course_id='course-v1:edX+DemoX+Demo_Course')
        self.course = self.course_run.course

        # Add a backing discovery course run so that preview_url is not None
        person = PersonFactory()
        CourseRunFactory(key=self.course_run.lms_course_id, staff=[person])

        self._generate_seats([Seat.AUDIT, Seat.HONOR, Seat.VERIFIED, Seat.PROFESSIONAL])
        self._generate_credit_seat()
        self.page_url = reverse('publisher:publisher_course_run_detail', args=[self.course_run.id])
        self.wrapped_course_run = CourseRunWrapper(self.course_run)
        self.date_format = '%b %d, %Y, %H:%M:%S %p'
        # initialize the state
        self.course_run_state = factories.CourseRunStateFactory(
            course_run=self.course_run, owner_role=PublisherUserRole.CourseTeam
        )
        self.course_state = factories.CourseStateFactory(
            course=self.course, owner_role=PublisherUserRole.CourseTeam
        )
        self.course_state.name = CourseStateChoices.Approved
        self.course_state.save()
        self.course_run.staff.add(PersonFactory())

    def test_page_without_login(self):
        """ Verify that user can't access detail page when not logged in. """
        self.client.logout()
        response = self.client.get(reverse('publisher:publisher_course_run_detail', args=[self.course_run.id]))

        self.assertRedirects(
            response,
            expected_url='{url}?next={next}'.format(
                url=reverse('login'),
                next=reverse('publisher:publisher_course_run_detail', args=[self.course_run.id])
            ),
            status_code=302,
            target_status_code=302
        )

    def test_page_without_data(self):
        """
        Verify that user can access detail page without any data
        available for that course-run.
        """
        course_run = factories.CourseRunFactory(course=self.course)
        factories.CourseRunStateFactory(course_run=course_run)
        assign_perm(
            OrganizationExtension.VIEW_COURSE_RUN, self.organization_extension.group, self.organization_extension
        )
        page_url = reverse('publisher:publisher_course_run_detail', args=[course_run.id])
        response = self.client.get(page_url)
        self.assertEqual(response.status_code, 200)
        self._assert_breadcrumbs(response, course_run)

    def test_page_with_invalid_id(self):
        """ Verify that invalid course run id return 404. """
        page_url = reverse('publisher:publisher_course_run_detail', args=[3434])
        response = self.client.get(page_url)
        self.assertEqual(response.status_code, 404)

    def _generate_seats(self, modes):
        """ Helper method to add seats for a course-run. """
        for mode in modes:
            factories.SeatFactory(type=mode, course_run=self.course_run)

    def _generate_credit_seat(self):
        """ Helper method to add credit seat for a course-run. """
        factories.SeatFactory(type='credit', course_run=self.course_run, credit_provider='ASU', credit_hours=9)

    def test_course_run_detail_page_staff(self):
        """
        Verify that detail page contains all the data for drupal, studio and
        cat with publisher admin user.
        """
        response = self.client.get(self.page_url)
        self.assertEqual(response.status_code, 200)
        self._assert_credits_seats(response, self.wrapped_course_run.credit_seat)
        self._assert_non_credits_seats(response, self.wrapped_course_run.non_credit_seats)
        self._assert_studio_fields(response)
        self._assert_cat(response)
        self._assert_drupal(response)
        self._assert_breadcrumbs(response, self.course_run)

        # assert person name appearing with url.
        person = self.course_run.staff.all()[0]
        self.assertContains(
            response, '<a href="{url}" target="_blank">{name}</a>'.format(
                url=person.profile_url,
                name=person.full_name
            )
        )

        # assert context contains data for the instructor-pop
        staff = self.wrapped_course_run.course_staff[0]
        self.assertEqual(
            json.loads(response.context['course_staff_config']),
            {"{uuid}".format(uuid=staff['uuid']): staff}
        )

    def _assert_credits_seats(self, response, seat):
        """ Helper method to test to all credit seats. """
        self.assertContains(response, 'Credit Seats')
        self.assertContains(response, 'Credit Provider')
        self.assertContains(response, 'Price')
        self.assertContains(response, 'Currency')
        self.assertContains(response, 'Credit Hours')

        self.assertContains(response, seat.credit_provider)
        self.assertContains(response, seat.price)
        self.assertContains(response, seat.currency.name)
        self.assertContains(response, seat.credit_hours)

    def _assert_non_credits_seats(self, response, seats):
        """ Helper method to test to all non-credit seats. """
        self.assertContains(response, 'Enrollment Type')
        self.assertContains(response, 'Price')
        self.assertContains(response, 'Currency')
        self.assertContains(response, 'Upgrade Deadline (time in UTC)')

        for seat in seats:
            self.assertContains(response, seat.type)
            self.assertContains(response, seat.price)
            self.assertContains(response, seat.currency)

    def _assert_studio_fields(self, response):
        """ Helper method to test studio values and labels. """
        fields = [
            'Course Name', 'Organization', 'Number', 'Start Date', 'End Date', 'Pacing Type'
        ]
        for field in fields:
            self.assertContains(response, field)

        values = [
            self.wrapped_course_run.title, self.wrapped_course_run.number,
            self.course_run.pacing_type_temporary
        ]
        for value in values:
            self.assertContains(response, value)

        self._assert_dates(response)

    def _assert_drupal(self, response):
        """ Helper method to test drupal values and labels. """
        fields = [
            'Title', 'Number', 'Course ID', 'Price', 'Subtitle', 'Organization', 'Subject', 'XSeries',
            'Start Date (time in UTC)', 'End Date (time in UTC)', 'Self Paced', 'Staff', 'Estimated Effort',
            'Languages', 'Video Transcript Languages', 'Level', 'Full Description', "What You&#39;ll Learn",
            'Keywords', 'Sponsors', 'Enrollment Types', 'Learner Testimonials', 'FAQ', 'Course About Video',
            'Prerequisites'
        ]
        for field in fields:
            self.assertContains(response, field)

        values = [
            self.wrapped_course_run.title, self.wrapped_course_run.lms_course_id,
            self.wrapped_course_run.seat_price,
            self.wrapped_course_run.min_effort,
            self.wrapped_course_run.pacing_type_temporary, self.wrapped_course_run.persons,
            self.wrapped_course_run.max_effort, self.wrapped_course_run.language.name,
            self.wrapped_course_run.transcript_languages, self.wrapped_course_run.level_type,
            self.wrapped_course_run.expected_learnings, self.wrapped_course_run.course.learner_testimonial,
            self.wrapped_course_run.course.faq, self.wrapped_course_run.course.video_link,
            self.wrapped_course_run.course.prerequisites
        ]
        for value in values:
            self.assertContains(response, value)

        for seat in self.wrapped_course_run.wrapped_obj.seats.all():
            self.assertContains(response, seat.type)

    def _assert_cat(self, response):
        """ Helper method to test cat data. """
        fields = [
            'Course ID', 'Enrollment Types'
        ]
        values = [self.course_run.lms_course_id]
        for field in fields:
            self.assertContains(response, field)

        for value in values:
            self.assertContains(response, value)

    def _assert_dates(self, response):
        """ Helper method to test all dates. """
        for value in [self.course_run.start_date_temporary, self.course_run.end_date_temporary]:
            self.assertContains(response, value.strftime(self.date_format))

    def test_course_run_with_version(self):
        """
        Verify that a SEAT_VERSION course still shows enrollment
        track data, and an ENTITLEMENT_VERSION course does not
        """
        self.client.logout()
        self.client.login(username=self.user.username, password=USER_PASSWORD)

        # For SEAT_VERSION Enrollment Track should be shown
        self.course.version = Course.SEAT_VERSION
        self.course.save()
        response = self.client.get(self.page_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Enrollment Track')

        # For ENTITLEMENT_VERSION no Enrollment Track should be show
        self.course.version = Course.ENTITLEMENT_VERSION
        self.course.save()
        response = self.client.get(self.page_url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Enrollment Track')

    def test_detail_page_with_comments(self):
        """
        Verify that detail page contains all the data along with comments
        for course.
        """
        self.client.logout()
        self.client.login(username=self.user.username, password=USER_PASSWORD)

        comment = CommentFactory(content_object=self.course_run, user=self.user, site=self.site)
        response = self.client.get(self.page_url)
        self.assertEqual(response.status_code, 200)
        self._assert_credits_seats(response, self.wrapped_course_run.credit_seat)
        self._assert_non_credits_seats(response, self.wrapped_course_run.non_credit_seats)
        self._assert_studio_fields(response)
        self._assert_cat(response)
        self._assert_drupal(response)
        self.assertContains(response, comment.comment)
        self._assert_breadcrumbs(response, self.course_run)

        # test decline comment appearing on detail page also.
        decline_comment = CommentFactory(
            content_object=self.course_run,
            user=self.user, site=self.site, comment_type=CommentTypeChoices.Decline_Preview
        )
        response = self.client.get(self.page_url)
        self.assertContains(response, decline_comment.comment)
        self.assertContains(response, '<b>Preview Decline:</b>')

    def test_get_course_return_none(self):
        """ Verify that `PublisherPermissionMixin.get_course` return none
        if `publisher_object` doesn't have `course` attr.
        """
        non_staff_user, group = create_non_staff_user_and_login(self)  # pylint: disable=unused-variable
        page_url = reverse('publisher:publisher_course_run_detail', args=[self.course_run.id])
        with mock.patch.object(CourseRunDetailView, 'get_object', return_value=non_staff_user):
            response = self.client.get(page_url)
            self.assertEqual(response.status_code, 403)

    def test_detail_page_with_role_assignment(self):
        """ Verify that detail page contains role assignment data for internal user. """

        # Add users in internal user group
        pc_user = UserFactory()
        marketing_user = UserFactory()
        publisher_user = UserFactory()
        internal_user_group = Group.objects.get(name=INTERNAL_USER_GROUP_NAME)

        internal_user_group.user_set.add(*(self.user, pc_user, marketing_user, publisher_user))

        organization = OrganizationFactory()
        self.course.organizations.add(organization)
        factories.OrganizationExtensionFactory(organization=organization)

        roles = [role for role, __ in PublisherUserRole.choices]
        for user, role in zip([pc_user, marketing_user, publisher_user], roles):
            factories.CourseUserRoleFactory(course=self.course, user=user, role=role)

        response = self.client.get(self.page_url)

        expected_roles = get_course_role_widgets_data(
            self.user, self.course, self.course_run_state, 'publisher:api:change_course_run_state'
        )

        for expected_role in expected_roles:
            expected_role.get('user_list', []).sort(key=lambda u: u.id)
        for role_widget in response.context['role_widgets']:
            role_widget.get('user_list', []).sort(key=lambda u: u.id)

        # This call is flaky in Travis. It is reliable locally, but occasionally in our CI environment,
        # this call returns an array which is not guaranteed to have an order, we do some post-processing
        # to sort those fields in place to test for equivalence.
        self.assertEqual(response.context['role_widgets'], expected_roles)

    def test_detail_page_approval_widget_with_non_internal_user(self):
        """ Verify that user can see change approval widget. """

        # Create a user and assign course view permission.
        user = UserFactory()
        assign_perm(
            OrganizationExtension.VIEW_COURSE_RUN, self.organization_extension.group, self.organization_extension
        )
        user.groups.add(self.organization_extension.group)

        self.client.logout()
        self.client.login(username=user.username, password=USER_PASSWORD)

        response = self.client.get(self.page_url)

        self.assertIn('role_widgets', response.context)
        self.assertContains(response, 'REVIEWS')

    def test_details_page_with_edit_permission(self):
        """ Test that user can see edit button on course run detail page. """
        user = self._create_user_and_login(OrganizationExtension.VIEW_COURSE_RUN)
        organization = OrganizationFactory()
        self.course.organizations.add(organization)
        organization_extension = factories.OrganizationExtensionFactory(organization=organization)

        self.assert_can_edit_permission()

        factories.CourseUserRoleFactory(course=self.course, user=user, role=PublisherUserRole.CourseTeam)

        assign_perm(
            OrganizationExtension.VIEW_COURSE_RUN, organization_extension.group, organization_extension
        )
        assign_perm(
            OrganizationExtension.EDIT_COURSE_RUN, organization_extension.group, organization_extension
        )

        user.groups.add(organization_extension.group)
        self.assert_can_edit_permission(can_edit=True)

    def test_edit_permission_with_no_organization(self):
        """ Test that user can't see edit button on course run detail page
        if there is no organization in course.
        """
        self._create_user_and_login(OrganizationExtension.VIEW_COURSE_RUN)

        self.assert_can_edit_permission()

    def assert_can_edit_permission(self, can_edit=False):
        """ Dry method to assert can_edit permission. """
        response = self.client.get(self.page_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['can_edit'], can_edit)

    def _assert_breadcrumbs(self, response, course_run):
        """ Assert breadcrumbs are present in the response. """
        self.assertContains(response, '<li class="breadcrumb-item ">')
        self.assertContains(response, '<a href="/publisher/courses/">Courses</a>')
        page_url = reverse('publisher:publisher_course_detail', kwargs={'pk': course_run.course.id})
        self.assertContains(
            response,
            '<a href="{url}">{number}: {title}</a>'.format(
                url=page_url,
                number=course_run.course.number,
                title=course_run.course.title)
        )
        self.assertContains(response, '<li class="breadcrumb-item active">')
        self.assertContains(
            response, '{type}: {start}'.format(
                type=course_run.get_pacing_type_temporary_display(),
                start=course_run.start_date_temporary.strftime("%B %d, %Y")
            )
        )

    def _create_user_and_login(self, permission):
        """ Create user and login, also assign view permission for course
         and return the user.
         """
        user = UserFactory()
        user.groups.add(self.organization_extension.group)
        assign_perm(permission, self.organization_extension.group, self.organization_extension)

        self.client.logout()
        self.client.login(username=user.username, password=USER_PASSWORD)

        return user

    def test_tabs_for_course_team_user(self):
        """Verify that internal/admin user will see only one tab. """
        response = self.client.get(self.page_url)
        self.assertContains(response, '<button class="selected" data-tab="#tab-1">All</button>')
        response_string = response.content.decode('UTF-8')
        self.assertNotIn(response_string, '<button data-tab="#tab-2">STUDIO</button>')
        self.assertNotIn(response_string, '<button data-tab="#tab-3">CAT</button>')
        self.assertNotIn(response_string, '<button data-tab="#tab-4">DRUPAL</button>')
        self.assertNotIn(response_string, '<button data-tab="#tab-5">Salesforce</button>')

    def test_comments(self):
        """ Verify that user will see the comments widget """
        response = self.client.get(self.page_url)
        self.assertContains(response, '<div id="comments-widget" class="comment-container">')

    def test_approval_widget_on_course_run_detail_page(self):
        """ Verify that user will see the history widget on
        the course run detail page.
        """
        self.user.groups.add(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))
        response = self.client.get(self.page_url)
        self.assertContains(response, '<div id="approval-widget" class="approval-widget">')

    def test_course_run_approval_widget_for_course_team(self):
        """
        Verify that user can see approval widget on course detail page with `Send for Review` button.
        """
        self.user.groups.add(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))

        factories.CourseUserRoleFactory(
            course=self.course, user=self.user, role=PublisherUserRole.CourseTeam
        )

        new_user = UserFactory()
        factories.CourseUserRoleFactory(
            course=self.course, user=new_user, role=PublisherUserRole.ProjectCoordinator
        )

        response = self.client.get(self.page_url)

        # Verify that content is sent for review and user can see Reviewed button as disabled.
        self.assertContains(response, 'Send for Review')
        self.assertContains(response, 'days in ownership')
        self.assertContains(response, self.get_expected_data(CourseRunStateChoices.Review, disabled=True))

        self._data_for_review_button()

        response = self.client.get(self.page_url)

        # Verify that Reviewed button is enabled
        self.assertContains(response, self.get_expected_data(CourseRunStateChoices.Review))

    def test_course_approval_widget_for_marketing_team(self):
        """
        Verify that project coordinator can't see the `Send for Review` button.
        """
        factories.CourseUserRoleFactory(
            course=self.course, user=self.user, role=PublisherUserRole.ProjectCoordinator
        )

        new_user = UserFactory()
        factories.CourseUserRoleFactory(
            course=self.course, user=new_user, role=PublisherUserRole.CourseTeam
        )

        self._data_for_review_button()

        response = self.client.get(self.page_url)

        # Verify that review button is not visible
        self.assertNotIn('Send for Review', response.content.decode('UTF-8'))

    def get_expected_data(self, state_name, disabled=False):
        expected = '<button class="{}" data-change-state-url="{}" data-state-name="{}"{} type="button">'.format(
            'btn btn-neutral btn-change-state',
            reverse('publisher:api:change_course_run_state', kwargs={'pk': self.course_run.course_run_state.id}),
            state_name,
            ' disabled' if disabled else ''
        )

        return expected

    def _data_for_review_button(self):
        """ Method to enable the review button."""
        self.course_run.course_run_state.name = CourseRunStateChoices.Draft
        self.course_run.course_run_state.save()

        factories.SeatFactory(course_run=self.course_run, type=Seat.VERIFIED, price=2)
        language_tag = LanguageTag(code='te-st', name='Test Language')
        language_tag.save()
        self.course_run.transcript_languages.add(language_tag)
        self.course_run.language = language_tag
        self.course_run.is_micromasters = True
        self.course_run.micromasters_name = 'test'
        self.course_run.max_effort = None
        self.course_run.save()
        self.course_run.staff.add(PersonFactory())

    def test_parent_course_not_approved(self):
        """ Verify that if parent course is not approved than their will be a message
        shown on course run detail page that user can't submit for approval.
        """
        self.user.groups.add(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))

        response = self.client.get(self.page_url)
        self.assertNotContains(response, '<div class="parent-course-approval">')

        # change course state to review.
        self.course.course_state.name = CourseStateChoices.Review
        self.course.course_state.save()

        response = self.client.get(self.page_url)
        self.assertContains(response, '<div class="parent-course-approval">')

    def test_course_run_mark_as_reviewed(self):
        """
        Verify that user can see mark as reviewed button on course detail page.
        """
        self.course_run_state.name = CourseRunStateChoices.Review
        self.course_run_state.save()
        factories.CourseUserRoleFactory(
            course=self.course, user=self.user, role=PublisherUserRole.CourseTeam
        )
        factories.CourseUserRoleFactory(
            course=self.course, user=UserFactory(), role=PublisherUserRole.ProjectCoordinator
        )

        response = self.client.get(self.page_url)

        # Verify that content is sent for review and user can see `Mark as Reviewed` button.
        self.assertContains(response, 'Sent for Review')
        self.assertContains(response, '<span class="icon fa fa-check" aria-hidden="true">', count=1)
        self.assertContains(response, 'Mark as Reviewed')
        self.assertContains(response, self.get_expected_data(CourseRunStateChoices.Approved))

    def test_course_with_reviewed(self):
        """
        Verify that user can see approval widget on course detail page with `Reviewed`.
        """
        factories.CourseUserRoleFactory(
            course=self.course, user=self.user, role=PublisherUserRole.ProjectCoordinator
        )

        factories.CourseUserRoleFactory(
            course=self.course, user=UserFactory(), role=PublisherUserRole.CourseTeam
        )

        # To create history objects for both `Review` and `Approved` states
        self.course_run_state.name = CourseStateChoices.Review
        self.course_run_state.save()
        self.course_run_state.name = CourseStateChoices.Approved
        self.course_run_state.owner_role = PublisherUserRole.Publisher
        self.course_run_state.approved_by_role = PublisherUserRole.CourseTeam
        self.course_run_state.save()

        self.user.groups.add(self.organization_extension.group)
        assign_perm(OrganizationExtension.VIEW_COURSE, self.organization_extension.group, self.organization_extension)
        response = self.client.get(self.page_url)

        # Verify that content is marked as reviewed and user can see Reviewed status.
        self.assertNotContains(response, 'Mark as Reviewed')
        self.assertContains(response, 'Reviewed', count=1)
        self.assertContains(response, '<span class="icon fa fa-check" aria-hidden="true">', count=2)
        self.assertContains(response, 'Sent for Review', count=1)

    def test_preview_widget(self):
        """
        Verify that user can see preview widget on course detail page.
        """
        factories.CourseUserRoleFactory(
            course=self.course, user=self.user, role=PublisherUserRole.CourseTeam
        )
        factories.CourseUserRoleFactory(
            course=self.course, user=UserFactory(), role=PublisherUserRole.Publisher
        )
        self.course_run_state.name = CourseStateChoices.Approved
        self.course_run_state.save()

        self.user.groups.add(self.organization_extension.group)
        assign_perm(OrganizationExtension.VIEW_COURSE, self.organization_extension.group, self.organization_extension)
        response = self.client.get(self.page_url)

        self.assertContains(response, 'ABOUT PAGE PREVIEW')
        self.assertContains(response, '<button class="btn btn-neutral btn-preview btn-preview-accept" type="button">')
        self.assertContains(response, '<button class="btn btn-neutral btn-preview btn-preview-decline" type="button">')
        self.assertContains(response, 'Reason for declining preview:')
        self.assertContains(response, '<input type="button" value="Submit" class="btn btn-neutral btn-add-comment" />')

        self.course_run_state.preview_accepted = True
        self.course_run_state.owner_role = PublisherUserRole.Publisher
        self.course_run_state.save()

        response = self.client.get(self.page_url)

        self.assertNotContains(
            response, '<button class="btn btn-neutral btn-preview btn-preview-accept" type="button">'
        )
        self.assertNotContains(
            response, '<button class="btn btn-neutral btn-preview btn-preview-decline" type="button">'
        )
        self.assertContains(response, 'Accepted')

    def test_course_preview(self):
        """Verify that publisher user can see preview widget."""
        factories.CourseUserRoleFactory(course=self.course, user=self.user, role=PublisherUserRole.Publisher)
        self.course_run_state.name = CourseStateChoices.Approved
        self.course_run_state.save()

        self.user.groups.add(self.organization_extension.group)
        assign_perm(OrganizationExtension.VIEW_COURSE, self.organization_extension.group, self.organization_extension)

        preview_api_url = reverse('publisher:api:update_course_run', args=[self.course_run.id])

        response = self.client.get(self.page_url)
        self.assertContains(response, 'ABOUT PAGE PREVIEW')
        self.assertContains(
            response,
            '<button data-url="{url}" class="btn btn-neutral btn-edit-preview-url">'.format(url=preview_api_url)
        )

        # verify with out preview_url
        self.course_run.lms_course_id = None
        self.course_run.save()

        response = self.client.get(self.page_url)
        self.assertContains(response, 'ABOUT PAGE PREVIEW')
        self.assertContains(response, '<span>Not available</span>')
        self.assertNotContains(response, 'id="id-review-url"')

    def test_course_publish_button(self):
        """Verify that publisher user can see Publish button."""
        user_role = factories.CourseUserRoleFactory(
            course=self.course, user=self.user, role=PublisherUserRole.Publisher
        )
        self.course_run_state.owner_role = PublisherUserRole.Publisher
        self.course_run_state.name = CourseRunStateChoices.Approved
        self.course_run_state.preview_accepted = True
        self.course_run_state.save()

        self.user.groups.add(self.organization_extension.group)
        assign_perm(OrganizationExtension.VIEW_COURSE, self.organization_extension.group, self.organization_extension)

        response = self.client.get(self.page_url)
        self.assertContains(response, '<button class="btn-brand btn-base btn-publish"')

        user_role.role = PublisherUserRole.CourseTeam
        user_role.save()

        response = self.client.get(self.page_url)
        # Verify that course team user cannot se publish button.
        self.assertNotContains(response, '<button class="btn-brand btn-base btn-publish"')

    def test_course_published(self):
        """Verify that user can see Published status if course is published."""
        self.course_run_state.name = CourseRunStateChoices.Published
        self.course_run_state.preview_accepted = True
        self.course_run_state.save()

        self.user.groups.add(self.organization_extension.group)
        assign_perm(OrganizationExtension.VIEW_COURSE, self.organization_extension.group, self.organization_extension)

        response = self.client.get(self.page_url)
        history_object = self.course_run_state.history.filter(
            name=CourseRunStateChoices.Published
        ).order_by('-modified').first()
        expected = 'The About page for this course run was published on {publish_date}.'.format(
            publish_date=history_object.modified.strftime('%m/%d/%y')
        )
        self.assertContains(response, expected)
        self.assertNotContains(response, '<button class="btn-brand btn-base btn-publish"')

    def test_edit_permission_with_owner_role(self):
        """
        Test that user can see edit button if he has permission and has role for course.
        """

        course_team_role = factories.CourseUserRoleFactory(
            course=self.course, user=self.user, role=PublisherUserRole.CourseTeam
        )

        self.user.groups.add(self.organization_extension.group)
        assign_perm(OrganizationExtension.VIEW_COURSE_RUN, self.organization_extension.group,
                    self.organization_extension)
        assign_perm(OrganizationExtension.EDIT_COURSE_RUN, self.organization_extension.group,
                    self.organization_extension)

        # verify popup message will not added in context
        response = self.client.get(self.page_url)
        self.assertEqual(response.context['can_edit'], True)
        self.assertNotIn('add_warning_popup', response.context)
        self.assertNotIn('current_team_name', response.context)
        self.assertNotIn('team_name', response.context)

        # Assign new user to course team role.
        course_team_role.user = UserFactory()
        course_team_role.save()

        # Verify that user cannot see edit button if he has no role for course.
        self.assert_can_edit_permission(can_edit=False)


# pylint: disable=attribute-defined-outside-init
@ddt.ddt
class CourseRunListViewTests(SiteMixin, TestCase):
    def setUp(self):
        super(CourseRunListViewTests, self).setUp()
        Site.objects.exclude(id=self.site.id).delete()
        self.group_internal = Group.objects.get(name=INTERNAL_USER_GROUP_NAME)
        self.group_project_coordinator = Group.objects.get(name=PROJECT_COORDINATOR_GROUP_NAME)
        self.group_reviewer = Group.objects.get(name=REVIEWER_GROUP_NAME)

        self.user1 = UserFactory()
        self.user2 = UserFactory()

        self.user1.groups.add(self.group_internal)
        self.user1.groups.add(self.group_project_coordinator)
        self.user1.groups.add(self.group_reviewer)
        self.user2.groups.add(self.group_internal)

        self.client.login(username=self.user1.username, password=USER_PASSWORD)
        self.page_url = reverse('publisher:publisher_dashboard')

        pc = PublisherUserRole.ProjectCoordinator

        # user1 courses data set ( 2 studio-request, 1 published, 1 in preview ready, 1 in progress )
        self.course_run_1 = self._create_course_assign_role(CourseRunStateChoices.Draft, self.user1, pc)
        self.course_run_2 = self._create_course_assign_role(CourseRunStateChoices.Approved, self.user1, pc)

        # mark course run 2 as in preview by creating a backing discovery course run, which defines preview_url
        self.course_run_2.lms_course_id = 'course-v1:edX+DemoX+Demo_Course'
        self.course_run_2.save()
        CourseRunFactory(key=self.course_run_2.lms_course_id, course=CourseFactory(partner=self.partner))

        self.course_run_3 = self._create_course_assign_role(CourseRunStateChoices.Published, self.user1, pc)
        self.course_run_4 = self._create_course_assign_role(
            CourseRunStateChoices.Draft, self.user1, PublisherUserRole.MarketingReviewer
        )

        # user2 courses
        self._create_course_assign_role(CourseRunStateChoices.Draft, self.user2, pc)
        self.table_class = "data-table-{id} display"

        # admin user can see all courses.

    def _create_course_assign_role(self, state, user, role):
        """ Create course-run-state, course-user-role and return course-run. """
        course = factories.CourseFactory(
            primary_subject=SubjectFactory(partner=self.partner),
            secondary_subject=SubjectFactory(partner=self.partner),
            tertiary_subject=SubjectFactory(partner=self.partner)
        )
        course_run = factories.CourseRunFactory(course=course)
        course_run_state = factories.CourseRunStateFactory(
            name=state,
            owner_role=role,
            course_run=course_run
        )

        factories.CourseUserRoleFactory(course=course_run_state.course_run.course, role=role, user=user)
        return course_run_state.course_run

    def test_page_without_login(self):
        """ Verify that user can't access course runs list page when not logged in. """
        self.client.logout()
        response = self.client.get(self.page_url)

        self.assertRedirects(
            response,
            expected_url='{url}?next={next}'.format(
                url=reverse('login'),
                next=self.page_url
            ),
            status_code=302,
            target_status_code=302
        )

    def test_un_authorize_group_user_cannot_view_courses(self):
        """ Verify that user from un-authorize group can access only that group courses. """
        self.client.logout()
        self.client.login(username=UserFactory(), password=USER_PASSWORD)
        response = self.assert_dashboard_response(
            studio_count=0, published_count=0, progress_count=0, preview_count=0
        )
        self._assert_tabs_with_roles(response)

    @ddt.data('progress', 'preview', 'studio', 'published')
    def test_with_internal_group(self, tab):
        """ Verify that internal user can see courses assigned to the groups. """
        response = self.assert_dashboard_response(
            studio_count=1, published_count=1, progress_count=2, preview_count=1
        )
        self.assertContains(response, '<li role="tab" id="tab-{tab}" class="tab"'.format(tab=tab))

    def test_with_permissions(self):
        """ Verify that user can view only those courses on which user group have permissions assigned. """
        self.client.logout()
        user = UserFactory()
        self.client.login(username=user.username, password=USER_PASSWORD)

        self.organization_extension = factories.OrganizationExtensionFactory()
        assign_perm(OrganizationExtension.VIEW_COURSE, self.organization_extension.group, self.organization_extension)
        self.course_run_1.course.organizations.add(self.organization_extension.organization)

        response = self.assert_dashboard_response(
            studio_count=0, published_count=0, progress_count=0, preview_count=0
        )
        self._assert_tabs_with_roles(response)

    def test_with_permissions_with_data(self):
        """ Verify that user with assigned permission on course can see all tabs
        with all course runs from all groups.
        """
        self.client.logout()
        user = UserFactory()

        self.client.login(username=user.username, password=USER_PASSWORD)

        self.organization_extension = factories.OrganizationExtensionFactory()

        self.course_run_1.course.organizations.add(self.organization_extension.organization)
        self.course_run_2.course.organizations.add(self.organization_extension.organization)
        self.course_run_4.course.organizations.add(self.organization_extension.organization)

        user.groups.add(self.organization_extension.group)
        assign_perm(
            OrganizationExtension.VIEW_COURSE, self.organization_extension.group, self.organization_extension
        )

        response = self.assert_dashboard_response(
            studio_count=0, published_count=0, progress_count=2, preview_count=1
        )
        self._assert_tabs_with_roles(response)

    def test_studio_request_course_runs_as_pc(self):
        """ Verify that PC user can see only those courses on which he is assigned as PC role. """
        response = self.assert_dashboard_response(
            studio_count=1, published_count=1, progress_count=2, preview_count=1
        )
        self._assert_tabs_with_roles(response)

    def test_studio_request_course_runs_without_pc_group(self):
        """ Verify that PC user can see only those courses on which he is assigned as PC role. """
        self.user1.groups.remove(self.group_project_coordinator)
        response = self.assert_dashboard_response(
            studio_count=0, published_count=1, progress_count=2, preview_count=1
        )
        self._assert_tabs_with_roles(response)

    def test_without_studio_request_course_runs(self):
        """ Verify that studio tab indicates a message if no course-run available. """
        self.course_run_1.lms_course_id = 'test-1'
        self.course_run_1.save()
        self.course_run_2.lms_course_id = 'test-2'
        self.course_run_2.save()
        response = self.assert_dashboard_response(
            studio_count=0, published_count=1, progress_count=2, preview_count=1
        )
        self.assertContains(response, 'No courses are currently ready for a Studio URL.')

    def test_without_published_course_runs(self):
        """ Verify that published tab indicates a message if no course-run available. """
        self.course_run_3.course_run_state.name = CourseRunStateChoices.Draft
        self.course_run_3.course_run_state.save()
        response = self.assert_dashboard_response(
            studio_count=2, published_count=0, progress_count=3, preview_count=1
        )
        self.assertContains(response, 'No About pages have been published yet')
        self._assert_tabs_with_roles(response)

    def test_published_course_runs(self):
        """ Verify that published tab loads course runs list. """
        response = self.assert_dashboard_response(
            studio_count=1, published_count=1, progress_count=2, preview_count=1
        )
        self.assertContains(response, self.table_class.format(id='published'))
        self.assertContains(response, 'About pages for the following course runs have been published in the')
        self._assert_tabs_with_roles(response)

    def test_published_course_runs_as_user_role(self):
        """
        Verify that user can see all published course runs as a user in a role for a course.
        """
        self.client.logout()

        internal_user = UserFactory()
        internal_user.groups.add(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))
        self.client.login(username=internal_user.username, password=USER_PASSWORD)

        # Verify that user cannot see any published course run
        self.assert_dashboard_response(
            studio_count=0, published_count=0, progress_count=0, preview_count=0
        )

        # assign user course role
        factories.CourseUserRoleFactory(
            course=self.course_run_3.course, user=internal_user, role=PublisherUserRole.ProjectCoordinator
        )

        # Verify that user can see 1 published course run
        response = self.assert_dashboard_response(
            studio_count=0, published_count=1, progress_count=0, preview_count=0
        )
        self._assert_tabs_with_roles(response)

    def test_published_course_runs_as_admin(self):
        """
        Verify that publisher admin can see all published course runs.
        """
        self.client.logout()

        publisher_admin = UserFactory()
        publisher_admin.groups.add(Group.objects.get(name=ADMIN_GROUP_NAME))
        self.client.login(username=publisher_admin.username, password=USER_PASSWORD)
        response = self.assert_dashboard_response(
            studio_count=3, published_count=1, progress_count=3, preview_count=1
        )
        self._assert_tabs_with_roles(response)

    def test_with_preview_ready_course_runs(self):
        """ Verify that preview ready tabs loads the course runs list. """
        response = self.assert_dashboard_response(
            studio_count=1, preview_count=1, progress_count=2, published_count=1
        )
        self.assertContains(response, self.table_class.format(id='preview'))
        self.assertContains(response, 'About page previews for the following course runs are available for course team')
        self._assert_tabs_with_roles(response)

    def test_without_preview_ready_course_runs(self):
        """ Verify preview ready tabs shows a message if no course run available. """
        self.course_run_2.lms_course_id = None
        self.course_run_2.save()
        self.course_run_2.course_run_state.name = CourseRunStateChoices.Draft
        self.course_run_2.course_run_state.save()
        response = self.assert_dashboard_response(
            studio_count=2, preview_count=0, progress_count=3, published_count=1
        )
        self._assert_tabs_with_roles(response)

    def test_without_preview_url(self):
        """ Verify in preview tab shows course in "in review" tab if course run is approve regardless of
        preview url is added or not.
        """
        response = self.assert_dashboard_response(
            studio_count=1, preview_count=1, progress_count=2, published_count=1
        )
        self._assert_tabs_with_roles(response)

        # without preview url
        self.course_run_2.lms_course_id = None
        self.course_run_2.save()
        response = self.assert_dashboard_response(
            studio_count=2, preview_count=1, progress_count=2, published_count=1
        )
        self._assert_tabs_with_roles(response)

    def test_with_in_progress_course_runs(self):
        """ Verify that in progress tabs loads the course runs list. """
        response = self.assert_dashboard_response(
            studio_count=1, preview_count=1, progress_count=2, published_count=1
        )
        self.assertContains(response, self.table_class.format(id='in-progress'))
        self._assert_tabs_with_roles(response)

    def assert_dashboard_response(self, studio_count=0, published_count=0, progress_count=0, preview_count=0):
        """ Dry method to assert the response."""
        response = self.client.get(self.page_url)

        self.assertEqual(response.status_code, 200)

        self.assertContains(response, 'Course About Pages')
        self.assertContains(response, 'EdX Publisher is used to create course About pages.')

        self.assertEqual(len(response.context['studio_request_courses']), studio_count)
        self.assertEqual(len(response.context['published_course_runs']), published_count)
        self.assertEqual(len(response.context['in_progress_course_runs']), progress_count)
        self.assertEqual(len(response.context['preview_course_runs']), preview_count)

        return response

    def _assert_tabs_with_roles(self, response):
        """ Dry method to assert the tabs data."""
        for tab in ['progress', 'preview', 'published']:
            self.assertContains(response, '<li role="tab" id="tab-{tab}" class="tab"'.format(tab=tab))

    def test_tabs_with_pc(self):
        """Verify that only pc use can see studio request tab on dashboard."""
        pc_user = UserFactory()
        pc_user.groups.add(Group.objects.get(name=PROJECT_COORDINATOR_GROUP_NAME))
        self.client.logout()
        self.client.login(username=pc_user.username, password=USER_PASSWORD)

        response = self.client.get(self.page_url)

        for tab in ['progress', 'preview', 'studio', 'published']:
            self.assertContains(response, '<li role="tab" id="tab-{tab}" class="tab"'.format(tab=tab))

    def test_site_name(self):
        """
        Verify that site_name is available in context.
        """
        response = self.client.get(self.page_url)
        site = Site.objects.first()
        self.assertEqual(response.context['site_name'], site.name)

    def test_filters(self):
        """
        Verify that filters available on dashboard.
        """
        course_team_user = UserFactory()
        course_run = self._create_course_assign_role(
            CourseRunStateChoices.Review, self.user1, PublisherUserRole.ProjectCoordinator
        )
        factories.CourseUserRoleFactory(
            course=course_run.course, role=PublisherUserRole.CourseTeam, user=course_team_user
        )
        course_run.course_run_state.owner_role = PublisherUserRole.CourseTeam
        course_run.course_run_state.save()

        response = self.client.get(self.page_url)

        self._assert_filter_counts(response, 'All', 3)
        self._assert_filter_counts(response, 'With Course Team', 2)
        self._assert_filter_counts(response, 'With {site_name}'.format(site_name=self.site.name), 1)

    def _assert_filter_counts(self, response, expected_label, count):
        """
        Assert label and course run count for filters.
        """
        self.assertContains(response, expected_label, count=1)
        expected_count = '<span class="filter-count">{count}</span>'.format(count=count)
        self.assertContains(response, expected_count, count=1)


class ToggleEmailNotificationTests(SiteMixin, TestCase):
    """ Tests for `ToggleEmailNotification` view. """

    def setUp(self):
        super(ToggleEmailNotificationTests, self).setUp()
        self.user = UserFactory()
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.toggle_email_settings_url = reverse('publisher:publisher_toggle_email_settings')

    def test_toggle_email_notification(self):
        """ Test that user can toggle email notification settings."""

        # Verify that by default email notification is enabled for the user
        self.assertEqual(is_email_notification_enabled(self.user), True)

        # Verify that user can disable email notifications
        self.assert_toggle_email_notification(False)

        # Verify that user can enable email notifications
        self.assert_toggle_email_notification(True)

    def assert_toggle_email_notification(self, is_enabled):
        """ Assert user can toggle email notifications."""
        response = self.client.post(self.toggle_email_settings_url, data={'is_enabled': json.dumps(is_enabled)})

        self.assertEqual(response.status_code, 200)

        # Reload user object from database to test the changes
        user = User.objects.get(username=self.user.username)

        self.assertEqual(is_email_notification_enabled(user), is_enabled)


class PaginationMixin:
    """
    Common methods to be used for Paginated views.
    """

    def get_courses(self, status_code=200, content_type='application/json', **kwargs):
        """
        Make get request with specified params.

        Arguments:
            status_code (int): used to verify the received response status code
            content_type (st): content type of get request
            kwargs (dict): extra kwargs like `query_params` to be used in get request

        Returns:
            courses (list): list of courses
        """
        query_params = kwargs.get('query_params', {})

        # draw query parameter is send by jquery DataTables in all ajax requests
        # https://datatables.net/manual/server-side
        draw = 1
        query_params['draw'] = draw

        response = self.client.get(self.courses_url, query_params, HTTP_ACCEPT=content_type)
        self.assertEqual(response.status_code, status_code)
        if content_type == 'application/json':
            json_response = response.json()
            self.assertEqual(json_response['draw'], draw)
            return json_response['courses']
        else:
            return json.loads(response.context_data['courses'].decode('utf-8'))


@ddt.ddt
class CourseListViewTests(SiteMixin, PaginationMixin, TestCase):
    """ Tests for `CourseListView` """

    def setUp(self):
        super(CourseListViewTests, self).setUp()
        self.courses = [factories.CourseFactory() for _ in range(10)]
        self.course = self.courses[0]
        self.user = UserFactory()

        for course in self.courses:
            factories.CourseStateFactory(course=course, owner_role=PublisherUserRole.MarketingReviewer)

        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.courses_url = reverse('publisher:publisher_courses')

    def test_courses_with_no_courses(self):
        """ Verify that user cannot see any course on course list page. """
        self.assert_course_list_page(course_count=0)

    def test_courses_with_admin(self):
        """ Verify that admin user can see all courses on course list page. """
        self.user.groups.add(Group.objects.get(name=ADMIN_GROUP_NAME))
        self.assert_course_list_page(course_count=10)

    def test_courses_with_course_user_role(self):
        """ Verify that internal user can see course on course list page. """
        self.user.groups.add(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))
        for course in self.courses:
            factories.CourseUserRoleFactory(course=course, user=self.user, role=InternalUserRole.Publisher)

        self.assert_course_list_page(course_count=10)

    def test_courses_with_permission(self):
        """ Verify that user can see course with permission on course list page. """
        organization_extension = factories.OrganizationExtensionFactory()
        self.user.groups.add(organization_extension.group)

        for course in self.courses:
            course.organizations.add(organization_extension.organization)

        assign_perm(OrganizationExtension.VIEW_COURSE, organization_extension.group, organization_extension)
        self.assert_course_list_page(course_count=10)

    def assert_course_list_page(self, course_count):
        """ Dry method to assert course list page content. """
        response = self.client.get(self.courses_url)

        self.assertContains(response, '{} Courses'.format(course_count))
        self.assertContains(response, 'Create New Course')
        if course_count > 0:
            self.assertEqual(response.status_code, 200)
            courses = json.loads(response.context_data['courses'].decode('utf-8'))
            self.assertIn(self.course.title, [course['course_title']['title'] for course in courses])

    def test_page_has_edit_button(self):
        """
        Verify that edit button is shown
        """
        organization_extension = factories.OrganizationExtensionFactory()
        self.course.organizations.add(organization_extension.organization)
        self.user.groups.add(organization_extension.group)
        factories.CourseUserRoleFactory(course=self.course, user=self.user, role=PublisherUserRole.CourseTeam)

        assign_perm(OrganizationExtension.VIEW_COURSE, organization_extension.group, organization_extension)
        assign_perm(OrganizationExtension.EDIT_COURSE, organization_extension.group, organization_extension)

        response = self.client.get(self.courses_url)
        self.assertContains(response, 'Edit')

    @ddt.data(
        {'search_text': 'N/A', 'expected': 1, 'owner_role': PublisherUserRole.CourseTeam},
        {'search_text': 'awaiting', 'expected': 11, 'owner_role': PublisherUserRole.MarketingReviewer},
        {'search_text': 'approved', 'expected': 1, 'owner_role': PublisherUserRole.CourseTeam,
         'marketing_reviewed': True},
    )
    @ddt.unpack
    def test_search_with_internal_user_status(self, search_text, expected, owner_role, marketing_reviewed=False):
        """
        Verify that search returns the correct data on course list page
        """
        self.user.groups.add(Group.objects.get(name=ADMIN_GROUP_NAME))
        self.course_state = factories.CourseStateFactory(owner_role=owner_role)
        self.course_state.marketing_reviewed = marketing_reviewed
        self.course_state.save()

        # Total number of courses without search
        self.assert_course_list_page(course_count=11)

        response = self.client.get(self.courses_url, {'searchText': search_text})
        courses = json.loads(response.context_data['courses'].decode('utf-8'))
        self.assertEqual(len(courses), expected)


@ddt.ddt
@mock.patch('course_discovery.apps.publisher.views.COURSES_DEFAULT_PAGE_SIZE', 2)
@mock.patch('course_discovery.apps.publisher.views.COURSES_ALLOWED_PAGE_SIZES', (2, 3, 4))
class CourseListViewPaginationTests(SiteMixin, PaginationMixin, TestCase):
    """ Pagination tests for `CourseListView` """

    def setUp(self):
        super(CourseListViewPaginationTests, self).setUp()
        self.courses = []
        self.course_titles = [
            'course title 16', 'course title 37', 'course title 19', 'course title 37', 'course title 25',
            'course title 25', 'course title 10', 'course title 13', 'course title 28', 'course title 13'
        ]
        self.course_organizations = [
            'zeroX', 'deepX', 'fuzzyX', 'arkX', 'maX', 'pizzaX', 'maX', 'arkX', 'fuzzyX', 'zeroX',
        ]
        self.course_dates = [
            datetime(2017, 1, 10), datetime(2019, 2, 25), datetime(2017, 3, 20), datetime(2018, 3, 24),
            datetime(2017, 2, 21), datetime(2015, 1, 22), datetime(2018, 2, 23), datetime(2017, 1, 21),
            datetime(2019, 1, 24), datetime(2017, 2, 11),
        ]
        # create 10 courses with related objects
        for index in range(10):
            course = factories.CourseFactory(title=self.course_titles[index],
                                             organizations=[OrganizationFactory(key=self.course_organizations[index])])
            for _ in range(random.randrange(1, 10)):
                factories.CourseRunFactory(course=course)

            course_state = factories.CourseStateFactory(course=course, owner_role=PublisherUserRole.MarketingReviewer)
            course_state.owner_role_modified = self.course_dates[index]
            course_state.save()

            self.courses.append(course)

        self.course = self.courses[0]
        self.user = UserFactory()
        self.user.groups.add(Group.objects.get(name=ADMIN_GROUP_NAME))

        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.courses_url = reverse('publisher:publisher_courses')

        self.sort_directions = {
            'asc': False,
            'desc': True,
        }

    @ddt.data(
        {'page_size': '', 'expected': 2},
        {'page_size': 2, 'expected': 2},
        {'page_size': 3, 'expected': 3},
        {'page_size': 4, 'expected': 4},
        {'page_size': -1, 'expected': 2},
    )
    @ddt.unpack
    def test_page_size(self, page_size, expected):
        """ Verify that page size is working as expected. """
        courses = self.get_courses(query_params={'pageSize': page_size})
        self.assertEqual(len(courses), expected)

    @ddt.data(
        {'page': '', 'expected': 1},
        {'page': 2, 'expected': 2},
        {'page': 10, 'expected': None},
    )
    @ddt.unpack
    def test_page_number(self, page, expected):
        """
        Verify that page number is working as expected.

        Note: We have total 3 pages. If page number is invalid than 404 response will be received.
        """
        response = self.client.get(self.courses_url, {'pageSize': 4, 'page': page})
        if response.status_code == 200:
            self.assertEqual(response.context_data['page_obj'].number, expected)
        else:
            self.assertEqual(response.status_code, 404)

    def test_content_type_text_html(self):
        """
        Verify that get request with text/html content type is working as expected.
        """
        courses = self.get_courses(content_type='text/html')
        self.assertEqual(len(courses), 2)

    @ddt.data(
        {'field': 'title', 'column': 0, 'direction': 'asc'},
        {'field': 'title', 'column': 0, 'direction': 'desc'},
    )
    @ddt.unpack
    def test_ordering_by_title(self, field, column, direction):
        """ Verify that ordering by title is working as expected. """
        for page in (1, 2, 3):
            courses = self.get_courses(
                query_params={'sortColumn': column, 'sortDirection': direction, 'pageSize': 4, 'page': page}
            )
            course_titles = [course['course_title'][field] for course in courses]
            self.assertEqual(sorted(course_titles, reverse=self.sort_directions[direction]), course_titles)

    @ddt.data(
        {'field': 'publisher_course_runs_count', 'column': 3, 'direction': 'asc'},
        {'field': 'publisher_course_runs_count', 'column': 3, 'direction': 'desc'},
    )
    @ddt.unpack
    def test_ordering_by_course_runs(self, field, column, direction):
        """ Verify that ordering by course runs is working as expected. """
        for page in (1, 2, 3):
            courses = self.get_courses(
                query_params={'sortColumn': column, 'sortDirection': direction, 'pageSize': 4, 'page': page}
            )
            course_runs = [course[field] for course in courses]
            self.assertEqual(sorted(course_runs, reverse=self.sort_directions[direction]), course_runs)

    def test_pagination_for_internal_user(self):
        """ Verify that pagination works for internal user. """
        with mock.patch('course_discovery.apps.publisher.models.is_publisher_admin', return_value=False):
            self.user.groups.add(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))
            self.course_team_role = factories.CourseUserRoleFactory(
                course=self.courses[0], user=self.user, role=PublisherUserRole.CourseTeam
            )
            self.course_team_role = factories.CourseUserRoleFactory(
                course=self.courses[1], user=self.user, role=PublisherUserRole.CourseTeam
            )
            courses = self.get_courses()
            self.assertEqual(len(courses), 2)

    def test_pagination_for_user_organizations(self):
        """ Verify that pagination works for user organizations. """
        with mock.patch('course_discovery.apps.publisher.models.is_publisher_admin', return_value=False):
            with mock.patch('course_discovery.apps.publisher.models.is_internal_user', return_value=False):
                organization_extension = factories.OrganizationExtensionFactory(
                    organization=self.courses[0].organizations.all()[0]  # zeroX
                )
                self.user.groups.add(organization_extension.group)
                assign_perm(OrganizationExtension.VIEW_COURSE, organization_extension.group, organization_extension)
                courses = self.get_courses()
                self.assertEqual(len(courses), 1)

    def test_context(self):
        """ Verify that required data is present in context. """
        with mock.patch('course_discovery.apps.publisher.views.COURSES_ALLOWED_PAGE_SIZES', COURSES_ALLOWED_PAGE_SIZES):
            response = self.client.get(self.courses_url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context_data['publisher_courses_url'], reverse('publisher:publisher_courses'))
            self.assertEqual(response.context_data['allowed_page_sizes'], json.dumps(COURSES_ALLOWED_PAGE_SIZES))

    @mock.patch('course_discovery.apps.publisher.models.CourseState.course_team_status', new_callable=mock.PropertyMock)
    @mock.patch('course_discovery.apps.publisher.models.CourseState.internal_user_status',
                new_callable=mock.PropertyMock)
    def test_course_state_exceptions(self, mocked_internal_user_status, mocked_course_team_status):
        """
        Verify that course_team_status and internal_user_status return
        default status when course.course_status does not exist.
        """
        mocked_internal_user_status.side_effect = ObjectDoesNotExist
        mocked_course_team_status.side_effect = ObjectDoesNotExist
        courses = self.get_courses()
        for course in courses:
            assert course['course_team_status'] == ''
            assert course['internal_user_status'] == ''

    @ddt.data(
        {'direction': 'asc'},
        {'direction': 'desc'},
    )
    @ddt.unpack
    def test_ordering_with_edx_status_column(self, direction):
        """
        Verify that ordering by edx status column is working as expected.
        """
        self.course_state = factories.CourseStateFactory(owner_role=PublisherUserRole.CourseTeam)
        self.course_state.marketing_reviewed = True
        self.course_state.save()

        for page in (1, 2, 3):
            courses = self.get_courses(
                query_params={'sortColumn': 6, 'sortDirection': direction, 'pageSize': 4, 'page': page}
            )
            internal_users_statuses = [course['internal_user_status'] for course in courses]
            self.assertEqual(sorted(internal_users_statuses,
                                    reverse=self.sort_directions[direction]),
                             internal_users_statuses)

    @ddt.data(
        {'direction': 'asc'},
        {'direction': 'desc'},
    )
    @ddt.unpack
    def test_ordering_with_course_number_column(self, direction):
        """
        Verify that ordering by course number column is working as expected.
        """

        for page in (1, 2, 3):
            courses = self.get_courses(
                query_params={'sortColumn': 1, 'sortDirection': direction, 'pageSize': 4, 'page': page}
            )
            course_numbers = [course['number'] for course in courses]
            self.assertEqual(sorted(course_numbers,
                                    key=lambda number: number.lower(),
                                    reverse=self.sort_directions[direction]),
                             course_numbers)


class CourseDetailViewTests(SiteMixin, TestCase):
    """ Tests for the course detail view. """

    def setUp(self):
        super(CourseDetailViewTests, self).setUp()
        self.organization_extension = factories.OrganizationExtensionFactory()
        self.course = factories.CourseFactory(organizations=[self.organization_extension.organization], image=None)
        self.user = UserFactory()
        self.client.login(username=self.user.username, password=USER_PASSWORD)

        # Initialize workflow for Course.
        self.course_state = factories.CourseStateFactory(course=self.course, owner_role=PublisherUserRole.CourseTeam)

        self.course_team_role = factories.CourseUserRoleFactory(
            course=self.course, user=self.user, role=PublisherUserRole.CourseTeam
        )

        self.detail_page_url = reverse('publisher:publisher_course_detail', args=[self.course.id])

    def test_detail_page_without_permission(self):
        """
        Verify that user cannot access course detail page without view permission.
        """
        response = self.client.get(self.detail_page_url)
        self.assertEqual(response.status_code, 403)

    def test_detail_page_with_permission(self):
        """
        Verify that user can access course detail page with view permission.
        """
        self.user.groups.add(self.organization_extension.group)
        assign_perm(OrganizationExtension.VIEW_COURSE, self.organization_extension.group, self.organization_extension)
        response = self.client.get(self.detail_page_url)
        self.assertEqual(response.status_code, 200)

    def test_detail_page_with_internal_user(self):
        """
        Verify that internal user can access course detail page.
        """
        self.user.groups.add(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))
        response = self.client.get(self.detail_page_url)
        self.assertEqual(response.status_code, 200)

    def test_detail_page_with_admin(self):
        """
        Verify that publisher admin can access course detail page.
        """
        self.user.groups.add(Group.objects.get(name=ADMIN_GROUP_NAME))
        response = self.client.get(self.detail_page_url)
        self.assertEqual(response.status_code, 200)

    def test_details_page_with_permissions(self):
        """ Test that user can see edit button on course detail page. """
        self.user.groups.add(self.organization_extension.group)
        assign_perm(OrganizationExtension.VIEW_COURSE, self.organization_extension.group, self.organization_extension)

        # Verify that user cannot see edit button without edit permission.
        self.assert_can_edit_permission(can_edit=False)

        assign_perm(OrganizationExtension.EDIT_COURSE, self.organization_extension.group, self.organization_extension)

        # Verify that user can see edit button with edit permission.
        self.assert_can_edit_permission(can_edit=True)

    def assert_can_edit_permission(self, can_edit):
        """ Dry method to assert can_edit permission. """
        response = self.client.get(self.detail_page_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['can_edit'], can_edit)

    def test_details_page_with_course_runs(self):
        """ Test that user can see course runs on course detail page. """
        self.user.groups.add(self.organization_extension.group)
        assign_perm(OrganizationExtension.VIEW_COURSE, self.organization_extension.group, self.organization_extension)

        course_run = factories.CourseRunFactory(course=self.course)

        response = self.client.get(self.detail_page_url)
        self.assertContains(response, 'COURSE RUNS')
        self.assertContains(response, 'CREATE RUN')
        self.assertContains(response, 'STUDIO URL -')
        self.assertContains(response, 'To be added by edX')
        self.assertContains(response, reverse('publisher:publisher_course_run_detail', kwargs={'pk': course_run.id}))

    def test_detail_page_data(self):
        """
        Verify that user can see course details on detail page.
        """
        self.user.groups.add(self.organization_extension.group)
        assign_perm(OrganizationExtension.VIEW_COURSE, self.organization_extension.group, self.organization_extension)
        response = self.client.get(self.detail_page_url)

        self.assertContains(response, self.course.title)
        self.assertContains(response, self.course.course_team_admin.full_name)
        self.assertContains(response, self.organization_extension.organization.name)
        self.assertContains(response, self.course.short_description)
        self.assertContains(response, self.course.full_description)
        self.assertContains(response, self.course.expected_learnings)
        self.assertContains(response, self.course.learner_testimonial)
        self.assertContains(response, self.course.faq)
        self.assertContains(response, self.course.video_link)
        self.assertContains(response, self.course.syllabus)
        assert response.context['breadcrumbs'][1]['slug'] == '{number}: {title}'.format(
            number=self.course.number,
            title=self.course.course_title)

    def test_details_page_with_course_runs_lms_id(self):
        """ Test that user can see course runs with lms-id on course detail page. """
        self.user.groups.add(self.organization_extension.group)
        assign_perm(OrganizationExtension.VIEW_COURSE, self.organization_extension.group, self.organization_extension)

        lms_course_id = 'test/id'
        factories.CourseRunFactory(course=self.course, lms_course_id=lms_course_id)
        response = self.client.get(self.detail_page_url)
        self.assertContains(response, 'course/{}'.format(lms_course_id))

    def test_page_has_approval_widget(self):
        """ Verify that user will see approval widget """
        self.user.groups.add(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))
        response = self.client.get(self.detail_page_url)
        self.assertContains(response, '<div id="approval-widget">')

    def test_comments(self):
        """ Verify that user will see the comments widget """
        self.user.groups.add(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))
        response = self.client.get(self.detail_page_url)
        self.assertContains(response, '<div id="comments-widget" class="comment-container">')

    def test_history_widget_on_course_detail_page(self):
        """ Verify that user will see the history widget on
        the course detail page.
        """
        # Update course to create multiple history objects.
        self.course.title = 'Updated Test Title'
        self.course.save()
        self.user.groups.add(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))
        response = self.client.get(self.detail_page_url)
        self.assertContains(response, '<div class="history-widget">')

    def test_approval_widget_on_course_detail_page(self):
        """ Verify that user will see the history widget on
        the course detail page.
        """
        self.user.groups.add(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))
        response = self.client.get(self.detail_page_url)
        self.assertContains(response, '<div class="approval-widget">')

    def test_course_approval_widget(self):
        """
        Verify that user can see approval widget on course detail page.
        """
        self.user.groups.add(self.organization_extension.group)
        assign_perm(OrganizationExtension.VIEW_COURSE, self.organization_extension.group, self.organization_extension)
        response = self.client.get(self.detail_page_url)

        self.assertContains(response, 'REVIEWS')
        self.assertContains(response, 'days in ownership')
        self.assertContains(response, 'Send for Review')
        self.assertContains(response, self.user.full_name)
        # Verify that `Send for Review` button is disabled
        self.assertContains(response, self.get_expected_data(CourseStateChoices.Review, disabled=True))

        # Enable `Send for Review` button by filling all required fields
        self.course.image = make_image_file('test_banner1.jpg')
        self.course.save()

        response = self.client.get(self.detail_page_url)
        # Verify that `Send for Review` button is enabled
        self.assertContains(response, self.get_expected_data(CourseStateChoices.Review))

    def test_course_with_mark_as_reviewed(self):
        """
        Verify that user can see approval widget on course detail page with `Mark as Reviewed`.
        """
        factories.CourseUserRoleFactory(
            course=self.course, user=self.user, role=PublisherUserRole.MarketingReviewer
        )
        self.course_state.owner_role = PublisherUserRole.MarketingReviewer
        self.course_state.name = CourseStateChoices.Review
        self.course_state.save()

        self.course_team_role.user = UserFactory()
        self.course_team_role.save()

        self.user.groups.add(self.organization_extension.group)
        assign_perm(OrganizationExtension.VIEW_COURSE, self.organization_extension.group, self.organization_extension)
        response = self.client.get(self.detail_page_url)

        # Verify that content is sent for review and user can see Reviewed button.
        self.assertContains(response, 'Mark as Reviewed')
        self.assertContains(response, '<span class="icon fa fa-check" aria-hidden="true">')
        self.assertContains(response, 'Sent for Review')
        self.assertContains(response, self.get_expected_data(CourseStateChoices.Approved))

    def get_expected_data(self, state_name, disabled=False):
        expected = '<button class="{}" data-change-state-url="{}" data-state-name="{}"{} type="button">'.format(
            'btn btn-neutral btn-change-state',
            reverse('publisher:api:change_course_state', kwargs={'pk': self.course.course_state.id}),
            state_name,
            ' disabled' if disabled else ''
        )

        return expected

    def test_course_with_reviewed(self):
        """
        Verify that user can see approval widget on course detail page with `Reviewed`.
        """
        self.course_team_role.user = UserFactory()
        self.course_team_role.save()

        factories.CourseUserRoleFactory(
            course=self.course, user=self.user, role=PublisherUserRole.MarketingReviewer
        )

        # To create history objects for both `Review` and `Approved` states
        self.course_state.name = CourseStateChoices.Review
        self.course_state.save()
        self.course_state.name = CourseStateChoices.Approved
        self.course_state.owner_role = PublisherUserRole.MarketingReviewer
        self.course_state.approved_by_role = PublisherUserRole.MarketingReviewer
        self.course_state.save()

        self.user.groups.add(self.organization_extension.group)
        assign_perm(OrganizationExtension.VIEW_COURSE, self.organization_extension.group, self.organization_extension)
        response = self.client.get(self.detail_page_url)

        # Verify that content is marked as reviewed and user can see Reviewed status.
        self.assertNotContains(response, 'Mark as Reviewed')
        self.assertContains(response, 'Reviewed', count=1)
        self.assertContains(response, '<span class="icon fa fa-check" aria-hidden="true">', count=2)
        self.assertContains(response, 'Sent for Review', count=1)

        self.course_state.marketing_reviewed = True
        self.course_state.owner_role = PublisherUserRole.CourseTeam
        self.course_state.save()

        response = self.client.get(self.detail_page_url)

        # Verify that content is marked as reviewed by both marketing and course team.
        self.assertNotContains(response, 'Send for Review')
        self.assertContains(response, 'Reviewed', count=2)

    def test_edit_permission_with_owner_role(self):
        """
        Test that user can see edit button if he has permission and has role for course.
        """
        self.course_state.owner_role = PublisherUserRole.MarketingReviewer
        self.course_state.save()

        factories.CourseUserRoleFactory(
            course=self.course, user=UserFactory(), role=PublisherUserRole.MarketingReviewer
        )

        self.user.groups.add(self.organization_extension.group)
        assign_perm(OrganizationExtension.VIEW_COURSE, self.organization_extension.group, self.organization_extension)
        assign_perm(OrganizationExtension.EDIT_COURSE, self.organization_extension.group, self.organization_extension)

        # Verify that user can see edit button with edit permission.
        self.assert_can_edit_permission(can_edit=True)

        # Assign new user to course team role.
        self.course_team_role.user = UserFactory()
        self.course_team_role.save()

        # Verify that user cannot see edit button if he has no role for course.
        self.assert_can_edit_permission(can_edit=False)

    def test_detail_page_with_role_widgets(self):
        """
        Test that user can see only two role widgets `Course Team` and `Marketing`
        on detail page even if other roles exists for course.
        """
        factories.CourseUserRoleFactory(
            course=self.course, user=UserFactory(), role=PublisherUserRole.MarketingReviewer
        )
        factories.CourseUserRoleFactory(
            course=self.course, user=UserFactory(), role=PublisherUserRole.Publisher
        )

        self.user.groups.add(self.organization_extension.group)
        assign_perm(OrganizationExtension.VIEW_COURSE, self.organization_extension.group, self.organization_extension)
        assign_perm(OrganizationExtension.EDIT_COURSE, self.organization_extension.group, self.organization_extension)

        response = self.client.get(self.detail_page_url)

        self.assertContains(response, '<div class="role-widget">', 2)
        self.assertContains(response, '<strong>COURSE TEAM</strong>')
        self.assertContains(response, '<strong>MARKETING</strong>')
        self.assertNotContains(response, '<strong>PUBLISHER</strong>')

    def test_detail_page_with_history_widget(self):
        """
        Test that user can see history widget on detail page if history exists.
        """
        self.user.groups.add(self.organization_extension.group)
        assign_perm(OrganizationExtension.VIEW_COURSE, self.organization_extension.group, self.organization_extension)

        self.assertGreater(self.course.history.count(), 0)

        response = self.client.get(self.detail_page_url)

        self.assertContains(response, 'REVISION HISTORY')

    def test_detail_page_without_most_recent_revision(self):
        """
        Test that user can see history widget on detail page if history exists.
        """
        self._assign_user_permission()

        response = self.client.get(self.detail_page_url)
        self.assertNotIn('most_recent_revision_id', response.context)
        self.assertNotIn('accept_all_button', response.context)

    def test_detail_page_with_accept_button(self):
        """
        Test that user can see accept button and context has most recent revision id
        """
        self._assign_user_permission()

        # update course object through page so that it will create history objects properly.
        # otherwise history_user does not appear in table.
        self._post_data(self.organization_extension)
        self._post_data(self.organization_extension)

        response = self.client.get(self.detail_page_url)
        current_user_revision = self.course.history.latest().history_id
        self.assertEqual(response.context['most_recent_revision_id'], current_user_revision)
        self.assertNotIn('accept_all_button', response.context)

        # it will make another history object without any history_user object.
        self.course.save()
        response = self.client.get(self.detail_page_url)
        self.assertEqual(response.context['most_recent_revision_id'], current_user_revision)
        self.assertTrue(response.context['accept_all_button'])

    def test_detail_page_with_override_values(self):
        """
        Test that pages shows the override short description, full description and title.
        """
        short_description = 'Testing short description'
        full_description = 'Testing full description'
        title = 'Testing title'

        self._assign_user_permission()
        course_run = factories.CourseRunFactory(
            course=self.course, short_description_override=short_description,
            full_description_override=full_description, title_override=title
        )
        factories.CourseRunStateFactory(course_run=course_run, name=CourseRunStateChoices.Published)
        response = self.client.get(self.detail_page_url)
        self.assertContains(response, short_description)
        self.assertContains(response, full_description)
        self.assertContains(response, title)

    def _assign_user_permission(self):
        """ Assign permissions."""
        self.user.groups.add(self.organization_extension.group)
        assign_perm(OrganizationExtension.VIEW_COURSE, self.organization_extension.group, self.organization_extension)
        assign_perm(
            OrganizationExtension.EDIT_COURSE, self.organization_extension.group, self.organization_extension
        )

    def _post_data(self, organization_extension):
        """
        Generate post data and return.
        """
        post_data = model_to_dict(self.course)
        post_data.pop('image')
        post_data['team_admin'] = self.user.id
        post_data['organization'] = organization_extension.organization.id
        post_data['title'] = 'updated title'

        self.client.post(reverse('publisher:publisher_courses_edit', args=[self.course.id]), post_data)


@ddt.ddt
class CourseEditViewTests(SiteMixin, TestCase):
    """ Tests for the course edit view. """

    course_error_message = 'The page could not be updated. Make sure that all values are correct, then try again.'

    def setUp(self):
        super(CourseEditViewTests, self).setUp()
        self.organization_extension = factories.OrganizationExtensionFactory()
        self.course = factories.CourseFactory(organizations=[self.organization_extension.organization], image=None)
        self.user = UserFactory()
        self.course_team_user = UserFactory()
        self.client.login(username=self.user.username, password=USER_PASSWORD)

        # Initialize workflow for Course.
        CourseState.objects.create(course=self.course, owner_role=PublisherUserRole.CourseTeam)

        self.course_team_role = factories.CourseUserRoleFactory(
            course=self.course, role=PublisherUserRole.CourseTeam, user=self.user
        )
        self.organization_extension.group.user_set.add(*(self.user, self.course_team_user))

        self.edit_page_url = reverse('publisher:publisher_courses_edit', args=[self.course.id])
        self.course_detail_url = reverse('publisher:publisher_course_detail', kwargs={'pk': self.course.id})

    def test_redirect_on_bad_hostname(self):
        """ Verify that we redirect the user if the hostname doesn't match what we expect. """

        self.user.groups.add(Group.objects.get(name=ADMIN_GROUP_NAME))
        with mock.patch.object(HttpRequest, 'get_host', return_value='not-the-site'):
            response = self.client.get(self.edit_page_url)

        self.assertRedirects(
            response,
            expected_url='http://' + self.site.domain + self.edit_page_url,
            status_code=301
        )

    def test_edit_page_without_permission(self):
        """
        Verify that user cannot access course edit page without edit permission.
        """
        response = self.client.get(self.edit_page_url)
        self.assertEqual(response.status_code, 403)

    def test_edit_page_number_with_course_run(self):
        """
        Verify that the course team cannot edit course number if course has atleast one course run
        """
        self.user.groups.add(self.organization_extension.group)
        assign_perm(OrganizationExtension.EDIT_COURSE, self.organization_extension.group, self.organization_extension)
        factories.CourseRunFactory.create(
            course=self.course, lms_course_id='course-v1:edxTest+Test342+2016Q1', end=datetime.now() + timedelta(days=1)
        )
        response = self.client.get(self.edit_page_url)
        self.assertEqual(response.context['has_course_run'], True)

    def test_edit_page_number_without_course_run(self):
        """
        Verify that the course team can edit course number if course has no run
        """
        self.user.groups.add(self.organization_extension.group)
        assign_perm(OrganizationExtension.EDIT_COURSE, self.organization_extension.group, self.organization_extension)
        response = self.client.get(self.edit_page_url)
        self.assertEqual(response.context['has_course_run'], False)

    def test_edit_page_with_edit_permission(self):
        """
        Verify that user can access course edit page with edit permission.
        """
        self.user.groups.add(self.organization_extension.group)
        assign_perm(OrganizationExtension.EDIT_COURSE, self.organization_extension.group, self.organization_extension)
        response = self.client.get(self.edit_page_url)
        self.assertEqual(response.status_code, 200)

    def test_edit_page_with_internal_user(self):
        """
        Verify that internal user can access course edit page.
        """
        self.user.groups.add(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))
        response = self.client.get(self.edit_page_url)
        self.assertEqual(response.status_code, 200)

    def test_edit_page_with_admin(self):
        """
        Verify that publisher admin can access course edit page.
        """
        self.user.groups.add(Group.objects.get(name=ADMIN_GROUP_NAME))
        response = self.client.get(self.edit_page_url)
        self.assertEqual(response.status_code, 200)

    def test_update_course_with_admin(self):
        """
        Verify that publisher admin can update an existing course.
        """
        self.user.groups.add(Group.objects.get(name=ADMIN_GROUP_NAME))
        post_data = self._post_data(self.organization_extension)

        updated_course_title = 'Updated {}'.format(self.course.title)
        post_data['title'] = updated_course_title
        post_data['short_description'] = 'Testing description'

        self.assertNotEqual(self.course.title, updated_course_title)
        self.assertNotEqual(self.course.changed_by, self.user)

        self.AssertEditCourseSuccess(post_data)

        course = Course.objects.get(id=self.course.id)
        # Assert that course is updated.
        self.assertEqual(course.title, updated_course_title)
        self.assertEqual(course.changed_by, self.user)
        self.assertEqual(course.short_description, 'Testing description')

    def test_update_course_with_non_internal_user(self):
        """
        Verify that non-internal user cannot update the course.
        """
        self.client.logout()
        user = UserFactory()
        self.client.login(username=user.username, password=USER_PASSWORD)
        user.groups.add(self.organization_extension.group)

        post_data = self._post_data(self.organization_extension)

        response = self.client.post(self.edit_page_url, data=post_data)

        self.assertEqual(response.status_code, 403)

    def test_update_course_team_admin(self):
        """
        Verify that publisher user can update course team admin.
        """
        self._assign_permissions(self.organization_extension)
        self.assertEqual(self.course.course_team_admin, self.course_team_role.user)

        self.AssertEditCourseSuccess(self._post_data(self.organization_extension))
        self.assertEqual(self.course.course_team_admin, self.course_team_user)

    def test_update_course_organization(self):
        """
        Verify that publisher user can update course organization.
        """
        self._assign_permissions(self.organization_extension)

        # Create new OrganizationExtension and assign edit/view permissions.
        organization_extension = factories.OrganizationExtensionFactory()
        organization_extension.group.user_set.add(*(self.user, self.course_team_user))
        self._assign_permissions(organization_extension)

        self.assertEqual(self.course.organizations.first(), self.organization_extension.organization)

        self.AssertEditCourseSuccess(post_data=self._post_data(organization_extension))
        self.assertEqual(self.course.organizations.first(), organization_extension.organization)

    def _assign_permissions(self, organization_extension):
        """
        Assign View/Edit permissions to OrganizationExtension object.
        """
        assign_perm(OrganizationExtension.VIEW_COURSE, organization_extension.group, organization_extension)
        assign_perm(OrganizationExtension.EDIT_COURSE, organization_extension.group, organization_extension)

    def _post_data(self, organization_extension):
        """
        Generate post data and return.
        """
        post_data = model_to_dict(self.course)
        post_data.pop('image')
        post_data['team_admin'] = self.course_team_user.id
        post_data['organization'] = organization_extension.organization.id

        return post_data

    def test_update_course_with_state(self):
        """
        Verify that course state changed to `Draft` on updating.
        """
        self.client.logout()
        self.client.login(username=self.course_team_role.user.username, password=USER_PASSWORD)
        self._assign_permissions(self.organization_extension)

        self.course.course_state.name = CourseStateChoices.Review
        self.course.course_state.save()

        post_data = self._post_data(self.organization_extension)
        post_data['team_admin'] = self.course_team_role.user.id

        self.AssertEditCourseSuccess(post_data)
        course_state = CourseState.objects.get(id=self.course.course_state.id)
        self.assertEqual(course_state.name, CourseStateChoices.Draft)

    def test_edit_course_with_project_coordinator(self):
        """
        Verify that on editing the course as project coordinator the ownership and
        course state does not change.
        """
        project_coordinator = UserFactory()
        project_coordinator.groups.add(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))
        project_coordinator.groups.add(Group.objects.get(name=PROJECT_COORDINATOR_GROUP_NAME))
        factories.CourseUserRoleFactory(course=self.course, role=PublisherUserRole.ProjectCoordinator,
                                        user=project_coordinator)
        self.client.logout()
        self.client.login(username=project_coordinator.username, password=USER_PASSWORD)
        self._assign_permissions(self.organization_extension)

        self.course.course_state.name = CourseStateChoices.Review
        self.course.course_state.owner_role = PublisherUserRole.MarketingReviewer
        self.course.course_state.save()

        post_data = self._post_data(self.organization_extension)
        post_data['team_admin'] = self.course_team_role.user.id

        self.AssertEditCourseSuccess(post_data)
        course_state = CourseState.objects.get(id=self.course.course_state.id)
        self.assertEqual(course_state.name, CourseStateChoices.Review)
        self.assertEqual(course_state.owner_role, PublisherUserRole.MarketingReviewer)

    def test_edit_course_with_ownership_changed(self):
        """
        Verify that on editing course state changed to `Draft` and ownership changed
        to `CourseTeam` if course team user updating the course.
        """
        self.client.logout()
        self.client.login(username=self.course_team_role.user.username, password=USER_PASSWORD)
        self._assign_permissions(self.organization_extension)

        self.course.course_state.name = CourseStateChoices.Review
        self.course.course_state.owner_role = PublisherUserRole.MarketingReviewer
        self.course.course_state.save()

        post_data = self._post_data(self.organization_extension)
        post_data['team_admin'] = self.course_team_role.user.id

        self.AssertEditCourseSuccess(post_data)
        course_state = CourseState.objects.get(id=self.course.course_state.id)
        self.assertEqual(course_state.name, CourseStateChoices.Draft)
        self.assertEqual(course_state.owner_role, PublisherUserRole.CourseTeam)

    def test_edit_course_with_marketing_reviewed(self):
        """
        Verify that if marketing already reviewed the course and then course team editing the course,
        state does not change to `Draft` and ownership remains to `CourseTeam`.
        """
        self.client.logout()
        self.client.login(username=self.course_team_role.user.username, password=USER_PASSWORD)
        self._assign_permissions(self.organization_extension)

        self.course.course_state.name = CourseStateChoices.Review
        self.course.course_state.owner_role = PublisherUserRole.CourseTeam
        self.course.course_state.marketing_reviewed = True
        self.course.course_state.save()

        post_data = self._post_data(self.organization_extension)
        post_data['team_admin'] = self.course_team_role.user.id

        response = self.client.post(self.edit_page_url, data=post_data)

        self.assertRedirects(
            response,
            expected_url=reverse('publisher:publisher_course_detail', kwargs={'pk': self.course.id}),
            status_code=302,
            target_status_code=200
        )

        course_state = CourseState.objects.get(id=self.course.course_state.id)
        self.assertEqual(course_state.name, CourseStateChoices.Review)
        self.assertEqual(course_state.owner_role, PublisherUserRole.CourseTeam)

    def test_video_link_field(self):
        """
        Verify that only internal user can see video link field on course edit page.
        """
        self.user.groups.add(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))
        response = self.client.get(self.edit_page_url)
        self.assertContains(response, 'VIDEO LINK')

        # Verify that course team user cannot see video link field.
        self.user.groups.remove(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))
        self.user.groups.add(self.organization_extension.group)
        assign_perm(OrganizationExtension.EDIT_COURSE, self.organization_extension.group, self.organization_extension)
        response = self.client.get(self.edit_page_url)
        self.assertNotContains(response, 'VIDEO LINK')

    def test_update_course_with_empty_title(self):
        """
        Verify that page shows error if title field is empty.
        """
        self.user.groups.add(Group.objects.get(name=ADMIN_GROUP_NAME))
        post_data = self._post_data(self.organization_extension)
        self.AssertEditCourseSuccess(post_data)

        post_data['title'] = ''
        self.AssertEditFailedWithError(post_data, error='This field is required')

    def test_edit_page_with_revision_changes(self):
        """
        Verify that page contains the history object.
        """
        self.user.groups.add(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))

        self.course.title = "updated title"
        self.course.save()

        history_obj = self.course.history.first()
        response = self.client.get(self.edit_page_url + '?history_id={}'.format(history_obj.history_id))
        self.assertEqual(history_obj.history_id, response.context['history_object'].history_id)

    def test_edit_page_with_invalid_revision_id(self):
        """
        Verify that if history id is invalid then history object will be none.
        """
        self.user.groups.add(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))

        self.course.title = "updated title"
        self.course.save()

        response = self.client.get(self.edit_page_url + '?history_id={}'.format(100))
        self.assertIsNone(response.context['history_object'])

    def test_seat_version_course_edit_page(self):
        """
        Verify that a SEAT_VERSION Course that has course runs associated with it can be updated without changing
        the version, and can change the version as long as the Course Run Seat prices and types match the Course
        """
        self.user.groups.add(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))
        self.course.version = Course.SEAT_VERSION
        self.course.save()
        post_data = self._post_data(self.organization_extension)
        post_data['team_admin'] = self.course_team_role.user.id
        post_data['mode'] = ''

        course_run = factories.CourseRunFactory.create(
            course=self.course, lms_course_id='course-v1:edxTest+Test342+2016Q1', end=datetime.now() + timedelta(days=1)
        )

        factories.CourseRunStateFactory(course_run=course_run, name=CourseRunStateChoices.Draft)
        factories.CourseUserRoleFactory(course=self.course, role=PublisherUserRole.Publisher)
        factories.CourseUserRoleFactory(course=self.course, role=PublisherUserRole.ProjectCoordinator)

        # Test that this saves without seats after resetting this to Seat version
        self.course.version = Course.SEAT_VERSION
        self.course.save()

        post_data['mode'] = CourseEntitlementForm.PROFESSIONAL_MODE
        post_data['price'] = 1
        self.AssertEditCourseSuccess(post_data)

        # Clear out the seats created above and reset the version to test the mismatch cases
        course_run.seats.all().delete()
        self.course.version = Course.SEAT_VERSION
        self.course.save()
        verified_seat = factories.SeatFactory.create(course_run=course_run, type=Seat.VERIFIED, price=2)
        factories.SeatFactory(course_run=course_run, type=Seat.AUDIT, price=0)  # Create a seat, do not need to access

        # Verify that we can switch between NOOP_MODES
        for noop_mode in [''] + CourseEntitlementForm.NOOP_MODES:
            post_data['mode'] = noop_mode
            post_data['price'] = 0
            response = self.client.post(self.edit_page_url, data=post_data)
            self.assertRedirects(
                response,
                expected_url=reverse('publisher:publisher_course_detail', kwargs={'pk': self.course.id}),
                status_code=302,
                target_status_code=200
            )

        # Modify the Course to try and create CourseEntitlements differing from the CourseRun and Seat type
        post_data['mode'] = CourseEntitlementForm.PROFESSIONAL_MODE
        post_data['price'] = 2  # just a number different than what is used in the SeatFactory constructor

        response = self.client.post(self.edit_page_url, data=post_data)
        self.assertEqual(response.status_code, 400)

        # Modify the Course to try and create CourseEntitlements differing from the CourseRun and Seat price
        post_data['mode'] = CourseEntitlementForm.VERIFIED_MODE
        post_data['price'] = 1  # just a number different than what is used in the SeatFactory constructor

        response = self.client.post(self.edit_page_url, data=post_data)
        self.assertEqual(response.status_code, 400)

        # Modify the Course to try and create CourseEntitlement the same as the Course Run and Seat type and price
        post_data['mode'] = verified_seat.type
        post_data['price'] = verified_seat.price

        response = self.client.post(self.edit_page_url, data=post_data)

        self.assertRedirects(
            response,
            expected_url=reverse('publisher:publisher_course_detail', kwargs={'pk': self.course.id}),
            status_code=302,
            target_status_code=200
        )

    def test_entitlement_version_course_edit_page(self):
        """
        Verify that an ENTITLEMENT_VERSION Course cannot be reverted to a SEAT_RUN Course, but a Course can be updated
        """
        self.user.groups.add(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))
        self.course.version = Course.SEAT_VERSION
        self.course.save()
        post_data = self._post_data(self.organization_extension)
        post_data['team_admin'] = self.course_team_role.user.id
        post_data['mode'] = CourseEntitlementForm.VERIFIED_MODE
        post_data['price'] = 150

        self.AssertEditCourseSuccess(post_data)
        # Assert that trying to switch to Audit/Credit Course (and thus allowing Course Run Seat configuration) fails
        for noop_mode in [''] + CourseEntitlementForm.NOOP_MODES:
            post_data['mode'] = noop_mode
            post_data['price'] = 0
            response = self.client.post(self.edit_page_url, data=post_data)
            self.assertEqual(response.status_code, 400)

        # Assert that not setting a price for a verified course fails
        post_data['mode'] = CourseEntitlementForm.VERIFIED_MODE
        post_data['price'] = ''
        response = self.client.post(self.edit_page_url, data=post_data)
        self.assertEqual(response.status_code, 400)

        # Assert that changing the price for a course with a Verified Entitlement is allowed
        new_course = factories.CourseFactory()
        factories.CourseEntitlementFactory(course=new_course, mode=CourseEntitlement.VERIFIED)
        post_data['mode'] = CourseEntitlementForm.VERIFIED_MODE
        post_data['price'] = 1
        self.AssertEditCourseSuccess(post_data)

    def test_entitlement_changes(self):
        """
        Verify that an entitlement course's type or price changes take effect correctly
        """
        self.user.groups.add(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))
        factories.CourseUserRoleFactory.create(course=self.course, role=PublisherUserRole.Publisher)
        factories.CourseUserRoleFactory.create(course=self.course, role=PublisherUserRole.ProjectCoordinator)
        factories.CourseUserRoleFactory.create(course=self.course, role=PublisherUserRole.MarketingReviewer)

        # Initial course values via form
        course_data = self._post_data(self.organization_extension)
        course_data['team_admin'] = self.user.id
        course_data['mode'] = CourseEntitlement.VERIFIED
        course_data['price'] = 150
        self.AssertEditCourseSuccess(course_data)

        # New course run via form
        new_run_url = reverse('publisher:publisher_course_runs_new', kwargs={'parent_course_id': self.course.id})
        current_datetime = datetime.now(timezone('US/Central'))
        run_data = {
            'pacing_type': 'self_paced',
            'start': (current_datetime + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S'),
            'end': (current_datetime + timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S'),
        }
        response = self.client.post(new_run_url, run_data)
        self.assertEqual(response.status_code, 302)

        self.course.refresh_from_db()
        course_run = self.course.course_runs.first()

        # Sanity check that we have the expected entitlement & seats
        self.assertEqual(CourseEntitlement.objects.count(), 1)
        self.assertEqual(Seat.objects.count(), 2)

        # Test price change
        course_data['mode'] = CourseEntitlement.VERIFIED
        course_data['price'] = 99
        self.AssertEditCourseSuccess(course_data)
        # Use this query because we delete the original records
        entitlement = CourseEntitlement.objects.get(course=self.course)  # Should be only one entitlement for the Course
        paid_seat = Seat.objects.get(type=Seat.VERIFIED, course_run=course_run)
        audit_seat = Seat.objects.get(type=Seat.AUDIT, course_run=course_run)
        self.assertEqual(entitlement.price, 99)
        self.assertEqual(paid_seat.price, 99)
        self.assertEqual(audit_seat.price, 0)

        # Test mode change
        course_data['mode'] = CourseEntitlement.PROFESSIONAL
        self.AssertEditCourseSuccess(course_data)
        paid_seat = Seat.objects.get(course_run=course_run)  # Should be only one seat now (no Audit seat)
        entitlement = CourseEntitlement.objects.get(course=self.course)  # Should be only one entitlement for the Course
        self.assertEqual(entitlement.mode, CourseEntitlement.PROFESSIONAL)
        self.assertEqual(paid_seat.type, Seat.PROFESSIONAL)

        # Test mode and price change again after saving but BEFORE publishing
        course_data['mode'] = CourseEntitlement.VERIFIED
        course_data['price'] = 1000
        self.AssertEditCourseSuccess(course_data)
        # There should be both an audit seat and a verified seat
        audit_seat = Seat.objects.get(course_run=course_run, type=Seat.AUDIT)
        verified_seat = Seat.objects.get(course_run=course_run, type=Seat.VERIFIED)
        entitlement = CourseEntitlement.objects.get(course=self.course)  # Should be only one entitlement for the Course
        self.assertNotEqual(audit_seat, None)
        self.assertEqual(entitlement.mode, CourseEntitlement.VERIFIED)
        self.assertEqual(entitlement.price, 1000)
        self.assertEqual(verified_seat.type, Seat.VERIFIED)
        self.assertEqual(verified_seat.price, 1000)

    def test_entitlement_published_run(self):
        """
        Verify that a course with a published course run cannot be saved with altered enrollment-track,
        but only price can be saved without changing the enrollment-track.
        """
        self.client.logout()
        self.client.login(username=self.course_team_role.user.username, password=USER_PASSWORD)
        self._assign_permissions(self.organization_extension)

        self.course.version = Course.ENTITLEMENT_VERSION
        self.course.save()
        verified_entitlement = factories.CourseEntitlementFactory(
            course=self.course, mode=CourseEntitlement.VERIFIED, price=100
        )
        course_run = factories.CourseRunFactory.create(
            course=self.course, lms_course_id='course-v1:edxTest+Test342+2016Q1', end=datetime.now() + timedelta(days=1)
        )
        factories.CourseRunStateFactory(course_run=course_run, name=CourseRunStateChoices.Published)
        factories.CourseUserRoleFactory(course=self.course, role=PublisherUserRole.Publisher)
        factories.CourseUserRoleFactory(course=self.course, role=PublisherUserRole.ProjectCoordinator)
        # Create a Verified and Audit seat
        factories.SeatFactory.create(course_run=course_run, type=Seat.VERIFIED, price=100)
        factories.SeatFactory(course_run=course_run, type=Seat.AUDIT, price=0)

        # Success case, price can be updated without changing enrollment track
        post_data = self._post_data(self.organization_extension)
        post_data['team_admin'] = self.course_team_role.user.id
        post_data['faq'] = 'Test FAQ Content'
        post_data['price'] = 50
        post_data['mode'] = verified_entitlement.mode
        self.AssertEditCourseSuccess(post_data)

        # Verify that when start date is None it didn't raise server error
        self.course.course_runs.update(start=None)
        self.AssertEditCourseSuccess(post_data)

        # Failure case when enrollment track is tried to change
        post_data = self._post_data(self.organization_extension)
        post_data['team_admin'] = self.course_team_role.user.id
        post_data['mode'] = CourseEntitlement.PROFESSIONAL
        response = self.client.post(self.edit_page_url, data=post_data)
        self.assertEqual(response.status_code, 400)

    @override_switch('enable_publisher_email_notifications', True)
    def test_course_with_published_course_run(self):
        """
        Verify that editing course with published course run does not changed state
        and an email is sent to Publisher.
        """
        self.client.logout()
        self.client.login(username=self.course_team_role.user.username, password=USER_PASSWORD)
        self._assign_permissions(self.organization_extension)

        self.course.course_state.name = CourseStateChoices.Approved
        self.course.course_state.save()

        course_run = factories.CourseRunFactory(course=self.course, lms_course_id='course-v1:edxTest+Test342+2016Q1')
        factories.CourseRunStateFactory(course_run=course_run, name=CourseRunStateChoices.Published)
        factories.CourseUserRoleFactory(course=self.course, role=PublisherUserRole.Publisher)
        factories.CourseUserRoleFactory(course=self.course, role=PublisherUserRole.ProjectCoordinator)

        post_data = self._post_data(self.organization_extension)
        post_data['number'] = 'testX654'

        self.AssertEditCourseSuccess(post_data)
        course_state = CourseState.objects.get(id=self.course.course_state.id)
        self.assertEqual(course_state.name, CourseStateChoices.Approved)

        # email send after editing.
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual([self.course.publisher.email], mail.outbox[0].to)

        course_key = CourseKey.from_string(course_run.lms_course_id)
        expected_subject = 'Changes to published course run: {title} {run_number}'.format(
            title=self.course.title,
            run_number=course_key.run
        )

        self.assertEqual(str(mail.outbox[0].subject), expected_subject)

    def AssertEditCourseSuccess(self, post_data):
        """Helper method to assert the course edit was successful"""
        response = self.client.post(self.edit_page_url, data=post_data)
        self.assertRedirects(response, expected_url=self.course_detail_url, status_code=302, target_status_code=200)
        self.assertNotContains(response, text=self.course_error_message, status_code=302)

    def AssertEditFailedWithError(self, post_data, error):
        """Helper method to assert the course edit was unsuccessful and with with an error"""
        response = self.client.post(self.edit_page_url, data=post_data)
        self.assertContains(response, self.course_error_message)
        self.assertContains(response, error)

    def _generate_random_html(self, max_length):
        """
        Generates a random html of specified length.
        """
        clean_text = ''
        random_html = """
        <html>
            <body>
                <h2>An Unordered HTML List</h2>
                <ul>
                    {}
                </ul>
            </body>
        </html>
        """.strip()

        while len(clean_text) < max_length:
            random_html = random_html.format('<li>Random LI </li>{}')
            clean_text = BeautifulSoup(random_html, 'html.parser').get_text(strip=True)
        return clean_text[:max_length]


@ddt.ddt
@override_switch('enable_publisher_email_notifications', True)
class CourseRunEditViewTests(SiteMixin, TestCase):
    """ Tests for the course run edit view. """

    def setUp(self):
        super(CourseRunEditViewTests, self).setUp()

        self.user = UserFactory()
        self.organization_extension = factories.OrganizationExtensionFactory(organization__partner=self.partner)
        self.group = self.organization_extension.group
        self.user.groups.add(self.group)

        self.group_project_coordinator = Group.objects.get(name=PROJECT_COORDINATOR_GROUP_NAME)

        self.course_run = factories.CourseRunFactory(course__organizations=[self.organization_extension.organization])
        self.course = self.course_run.course
        self.seat = factories.SeatFactory(course_run=self.course_run, type=Seat.VERIFIED, price=2)

        self.client.login(username=self.user.username, password=USER_PASSWORD)
        current_datetime = datetime.now(timezone('US/Central'))
        self.start_date_time = (current_datetime + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
        self.end_date_time = (current_datetime + timedelta(days=60)).strftime('%Y-%m-%d %H:%M:%S')

        # creating default organizations roles
        factories.OrganizationUserRoleFactory(
            role=PublisherUserRole.ProjectCoordinator, organization=self.organization_extension.organization
        )
        factories.OrganizationUserRoleFactory(
            role=PublisherUserRole.MarketingReviewer, organization=self.organization_extension.organization
        )

        # create a course instance using the new page so that all related objects created
        # in other tables also
        data = {'number': 'course_update_1', 'image': '', 'title': 'test course', 'url_slug': ''}
        self.user.groups.add(Group.objects.get(name=ADMIN_GROUP_NAME))
        course_dict = self._post_data(data, self.course, self.course_run)
        self.client.post(reverse('publisher:publisher_courses_new'), course_dict, files=data['image'])

        # newly created course from the page.
        self.new_course = Course.objects.get(number=data['number'])
        self.new_course_run = factories.CourseRunFactory(course=self.new_course)
        factories.CourseRunStateFactory(course_run=self.new_course_run, owner_role=PublisherUserRole.CourseTeam)

        assign_perm(OrganizationExtension.EDIT_COURSE_RUN, self.group, self.organization_extension)
        assign_perm(OrganizationExtension.VIEW_COURSE_RUN, self.group, self.organization_extension)

        # assert edit page is loading successfully.
        self.edit_page_url = reverse('publisher:publisher_course_runs_edit', kwargs={'pk': self.new_course_run.id})
        response = self.client.get(self.edit_page_url)
        self.assertEqual(response.status_code, 200)

        # Update the data for course
        data = {'full_description': 'This is testing description.', 'image': ''}
        self.updated_dict = self._post_data(data, self.new_course, self.new_course_run, self.seat)

        # Update the data for course-run
        self.updated_dict['is_xseries'] = True
        self.updated_dict['xseries_name'] = 'Test XSeries'

    def test_courserun_edit_form_for_course_with_entitlements(self):
        """ Verify that the edit form does not include Seat fields for courses that use entitlements. """
        self.course_run.course.version = Course.ENTITLEMENT_VERSION
        self.course_run.course.save()

        url = reverse('publisher:publisher_course_runs_edit', kwargs={'pk': self.course_run.id})
        response = self.client.get(url)
        self.assertNotContains(response, 'CERTIFICATE TYPE AND PRICE', status_code=200)

    def test_courserun_edit_form_for_course_without_entitlements(self):
        """ Verify that the edit form includes Seat fields for courses that do not use entitlements. """
        self.course_run.course.version = Course.SEAT_VERSION
        self.course_run.course.save()

        url = reverse('publisher:publisher_course_runs_edit', kwargs={'pk': self.course_run.id})
        response = self.client.get(url)
        self.assertContains(response, 'CERTIFICATE TYPE AND PRICE', status_code=200)

    def login_with_course_user_role(self, course_run, role=PublisherUserRole.CourseTeam):
        user = course_run.course.course_user_roles.get(role=role).user
        self.client.login(username=user.username, password=USER_PASSWORD)
        return user

    def assert_seats(self, course_run, expected_seat_count, expected_seats):
        """Helper method to assert expected course run seats"""
        course_run_seats = Seat.objects.filter(course_run=course_run).order_by('type')
        self.assertEqual(course_run_seats.count(), expected_seat_count)
        seat_types = [seat.type for seat in course_run_seats]
        self.assertEqual(seat_types, expected_seats)

    def test_edit_page_with_two_seats(self):
        """
        Verify that if a course run has both audit and verified seats, Verified seat is displayed
        on the course run edit page
        """
        factories.SeatFactory(course_run=self.course_run, type=Seat.AUDIT)
        self.edit_page_url = reverse('publisher:publisher_course_runs_edit', kwargs={'pk': self.course_run.id})
        response = self.client.get(self.edit_page_url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '<div id="seatPriceBlock" class="col col-6 hidden" style="display: block;">')

    def test_get_context_data_with_pc(self):
        """
        Verify that the get function returns empty list of organization_ids in the context
        if the logged in user is project coordinator
        """
        pc_user = UserFactory()
        pc_user.groups.add(self.group_project_coordinator)
        pc_user.groups.add(self.organization_extension.group)

        assign_perm(
            OrganizationExtension.EDIT_COURSE_RUN, self.organization_extension.group, self.organization_extension
        )
        self.client.logout()
        self.client.login(username=pc_user.username, password=USER_PASSWORD)
        self.edit_page_url = reverse('publisher:publisher_course_runs_edit', kwargs={'pk': self.course_run.id})
        response = self.client.get(self.edit_page_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['organizations_ids'], [])

    def _post_data(self, data, course, course_run, seat=None):
        course_dict = model_to_dict(course)
        course_dict.update(**data)
        course_dict['team_admin'] = self.user.id
        if course_run:
            course_dict.update(**model_to_dict(course_run))
            course_dict.pop('video_language')
            course_dict.pop('end')
            course_dict.pop('priority')
            course_dict['lms_course_id'] = ''
            course_dict['start'] = self.start_date_time
            course_dict['end'] = self.end_date_time
            course_dict['organization'] = self.organization_extension.organization.id
            if seat:
                course_dict.update(**model_to_dict(seat))

        course_dict.pop('id')
        return course_dict

    def test_edit_page_without_permission(self):
        """
        Verify that user cannot access course edit page without edit permission.
        """
        self.client.logout()
        create_non_staff_user_and_login(self)

        response = self.client.get(self.edit_page_url)
        self.assertEqual(response.status_code, 403)

    def test_edit_page_with_edit_permission(self):
        """
        Verify that user can access course edit page with edit permission.
        """
        self.user.groups.add(self.organization_extension.group)
        assign_perm(OrganizationExtension.EDIT_COURSE, self.organization_extension.group, self.organization_extension)
        response = self.client.get(self.edit_page_url)
        self.assertEqual(response.status_code, 200)

    def test_edit_page_with_internal_user(self):
        """
        Verify that internal user can access course edit page.
        """
        self.user.groups.add(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))
        response = self.client.get(self.edit_page_url)
        self.assertEqual(response.status_code, 200)

    def test_edit_page_with_admin(self):
        """
        Verify that publisher admin can access course edit page.
        """
        self.user.groups.add(Group.objects.get(name=ADMIN_GROUP_NAME))
        response = self.client.get(self.edit_page_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Edit Course')

    @ddt.data('start', 'end', 'pacing_type')
    def test_update_with_errors(self, field):
        """ Verify that course run edit page throws error in case of missing required field."""
        self.client.logout()
        user, __ = create_non_staff_user_and_login(self)

        self.assertNotEqual(self.course_run.changed_by, user)
        user.groups.add(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))

        self.updated_dict.pop(field)

        response = self.client.post(self.edit_page_url, self.updated_dict)

        self.assertEqual(response.status_code, 400)

    def test_update_with_fail_transaction(self):
        """ Verify that in case of any error transactions roll back and no object
        updated in db.
        """
        with mock.patch.object(CourseRun, "save") as mock_method:
            mock_method.side_effect = IntegrityError
            response = self.client.post(self.edit_page_url, self.updated_dict)

            self.assertEqual(response.status_code, 400)
            updated_course = Course.objects.get(id=self.new_course.id)
            self.assertNotEqual(updated_course.full_description, 'This is testing description.')

            course_run = CourseRun.objects.get(id=self.new_course_run.id)
            self.assertNotEqual(course_run.xseries_name, 'Test XSeries')

    @skip('flaky')
    def test_update_course_run_with_seat(self):
        """ Verify that course run edit page create seat object also if not exists previously."""
        user = self.login_with_course_user_role(self.new_course_run)
        self.assertNotEqual(self.course_run.changed_by, user)

        # post data without seat
        data = {'image': ''}
        updated_dict = self._post_data(data, self.new_course, self.new_course_run)
        updated_dict['type'] = Seat.PROFESSIONAL
        updated_dict['price'] = 10.00

        response = self.client.post(self.edit_page_url, updated_dict)

        self.assertRedirects(
            response,
            expected_url=reverse('publisher:publisher_course_run_detail', kwargs={'pk': self.new_course_run.id}),
            status_code=302,
            target_status_code=200
        )

        self.assert_seats(self.new_course_run, 1, [Seat.PROFESSIONAL])
        self.assertEqual(self.new_course_run.seats.first().price, 10)
        self.assertEqual(self.new_course_run.seats.first().history.all().count(), 1)

    def test_update_course_run_create_duplicate_seats(self):
        """
        Tests that course run seats are not duplicated when editing.
        Course run seats should remain consistent when updating seats.
        """
        self.login_with_course_user_role(self.new_course_run)
        data = {'image': '', 'type': Seat.VERIFIED, 'price': 10.00}
        post_data = self._post_data(data, self.new_course, self.new_course_run)

        self.client.post(self.edit_page_url, post_data)
        self.assert_seats(self.new_course_run, 2, [Seat.AUDIT, Seat.VERIFIED])

        post_data['price'] = 20.00
        self.client.post(self.edit_page_url, post_data)
        self.assert_seats(self.new_course_run, 2, [Seat.AUDIT, Seat.VERIFIED])
        self.assertEqual(self.new_course_run.paid_seats.first().price, 20.00)

    @ddt.data(Seat.VERIFIED, Seat.CREDIT)
    def test_cleanup_course_run_seats_bogus_data(self, seat_type):
        """
        Test that bogus course run seat data is corrected upon saving the
        course run.

        Some data in publisher has duplicate course seats, this tests that we are able
        to correct the data upon course run save.
        """
        # Login and verify the course run has no seats.
        self.login_with_course_user_role(self.new_course_run)
        self.assert_seats(self.new_course_run, 0, [])

        # create some bogus seats for the course run & verify the seats exists
        __ = [self.new_course_run.seats.create(type=seat_type) for _ in range(10)]
        self.new_course_run.refresh_from_db()
        self.assert_seats(self.new_course_run, 10, [seat_type] * 10)

        # Make course run save post request and verify the correct course seats.
        data = {'image': '', 'type': Seat.VERIFIED, 'price': 100.00}
        post_data = self._post_data(data, self.new_course, self.new_course_run)
        self.client.post(self.edit_page_url, post_data)
        # This call is flaky in Travis. It is reliable locally, but occasionally in our CI environment,
        # this call won't delete 8 of the 10 seats. The self.new_course_run.refresh_from_db() call should
        # hopefully fix this by having an explicit update occur before sending the data along via POST.
        self.assert_seats(self.new_course_run, 2, [Seat.AUDIT, Seat.VERIFIED])
        self.assertEqual(self.new_course_run.paid_seats.first().price, 100.00)

    def test_update_course_run_for_course_that_uses_entitlements(self):
        """ Verify that a user cannot change Seat data when editing courseruns for courses that use entitlements. """
        self.user.groups.add(Group.objects.get(name=ADMIN_GROUP_NAME))

        self.new_course.version = Course.ENTITLEMENT_VERSION
        self.new_course.save()

        post_data = self._post_data({}, self.new_course, self.new_course_run)
        post_data.update({'image': '', 'max_effort': 123, 'type': Seat.PROFESSIONAL, 'price': 10.00})

        # Create a Seat so we can verify that it does not get modified.
        before_seat = self.new_course_run.seats.create(type=Seat.VERIFIED, price=5)
        self.assertNotEqual(before_seat.type, post_data['type'])
        self.assertNotEqual(before_seat.price, post_data['price'])
        self.assertNotEqual(self.new_course_run.max_effort, post_data['max_effort'])

        # This request should fail since it includes Seat data
        response = self.client.post(self.edit_page_url, post_data)
        self.assertContains(response, 'The page could not be updated.', status_code=400)

        del post_data['type']
        del post_data['price']

        # Now that the Seat data has been removed, the request should succeed.
        response = self.client.post(self.edit_page_url, post_data)
        self.assertRedirects(
            response,
            expected_url=reverse('publisher:publisher_course_run_detail', kwargs={'pk': self.new_course_run.id}),
            status_code=302,
            target_status_code=200
        )

        # Make sure that max_effort was updated, but the Seat data was not.
        course_run = CourseRun.objects.get(id=self.new_course_run.id)
        self.assertEqual(post_data['max_effort'], course_run.max_effort)
        after_seat = course_run.seats.latest('created')
        self.assertEqual(before_seat.type, after_seat.type)
        self.assertEqual(before_seat.price, after_seat.price)

    def test_logging(self):
        """ Verify view logs the errors in case of errors. """
        with mock.patch('django.forms.models.BaseModelForm.is_valid') as mocked_is_valid:
            mocked_is_valid.return_value = True
            with LogCapture(publisher_views_logger.name) as log_capture:
                # pop the
                self.updated_dict.pop('start')
                response = self.client.post(self.edit_page_url, self.updated_dict)
                self.assertEqual(response.status_code, 400)
                log_capture.check(
                    (
                        publisher_views_logger.name,
                        'ERROR',
                        'Unable to update course run and seat for course [{}].'.format(self.new_course_run.id)
                    )
                )

    def test_update_course_run_with_edit_permission(self):
        """ Verify that internal users can update the data from course run edit page."""
        self.client.logout()
        user = UserFactory()
        user.groups.add(self.organization_extension.group)

        # assign the edit course run and view course run permission.
        assign_perm(
            OrganizationExtension.EDIT_COURSE_RUN, self.organization_extension.group, self.organization_extension
        )
        assign_perm(
            OrganizationExtension.VIEW_COURSE_RUN, self.organization_extension.group, self.organization_extension
        )

        self.client.login(username=user.username, password=USER_PASSWORD)

    def test_edit_page_with_language_tags(self):
        """
        Verify that publisher user can access course run edit page.
        """
        self.user.groups.add(Group.objects.get(name=ADMIN_GROUP_NAME))

        language_tag = LanguageTag(code='te-st', name='Test Language')
        language_tag.save()
        self.course_run.transcript_languages.add(language_tag)
        self.course_run.save()
        response = self.client.get(self.edit_page_url)
        self.assertEqual(response.status_code, 200)

    def test_update_moves_state_to_draft(self):
        """ Verify that in case of editing course-run state will change to draft."""
        # state will be change if the course-run state is other than draft.
        self.new_course_run.course_run_state.name = CourseRunStateChoices.Review
        self.new_course_run.course_run_state.save()
        self.new_course_run.refresh_from_db()
        self.assertEqual(self.new_course_run.course_run_state.name, CourseRunStateChoices.Review)
        response = self.client.post(self.edit_page_url, self.updated_dict)

        # This call is flaky in Travis. It is reliable locally, but occasionally in our CI environment,
        # this call won't redirect, and instead will return a 400. This can occur from any exception
        # being thrown, as well as any invalid form data. The self.new_course_run.refresh_from_db() call should
        # hopefully fix this by having an explicit update occur before sending the data along via POST.
        self.assertRedirects(
            response,
            expected_url=reverse('publisher:publisher_course_run_detail', kwargs={'pk': self.new_course_run.id}),
            status_code=302,
            target_status_code=200
        )

        course_run = CourseRun.objects.get(id=self.new_course_run.id)
        # state change to draft again.
        self.assertEqual(course_run.course_run_state.name, CourseRunStateChoices.Draft)

    def test_studio_instance_on_edit_page(self):
        """
        Verify that internal users can update course key from edit page.
        """
        response = self.client.get(self.edit_page_url)

        self.assertContains(response, 'Studio URL')
        self.assertContains(response, 'name="lms_course_id"')

        self.updated_dict['lms_course_id'] = 'course-v1:edxTest+Test342+2016Q1'

        response = self.client.post(self.edit_page_url, self.updated_dict)

        self.assertRedirects(
            response,
            expected_url=reverse('publisher:publisher_course_run_detail', kwargs={'pk': self.new_course_run.id}),
            status_code=302,
            target_status_code=200
        )

        self.new_course_run = CourseRun.objects.get(id=self.new_course_run.id)
        self.assertEqual(self.new_course_run.lms_course_id, self.updated_dict['lms_course_id'])

        course_key = CourseKey.from_string(self.new_course_run.lms_course_id)
        self.assert_email_sent(
            reverse('publisher:publisher_course_run_detail', kwargs={'pk': self.new_course_run.id}),
            'Studio URL created: {title} {run}'.format(title=self.new_course.title, run=course_key.run),
            'has created a Studio URL'
        )

    def test_effort_on_edit_page(self):
        """
        Verify that users can update course min_effort and max_effort from edit page.
        """

        self.updated_dict['min_effort'] = 2
        self.updated_dict['max_effort'] = 5

        response = self.client.post(self.edit_page_url, self.updated_dict)

        self.assertRedirects(
            response,
            expected_url=reverse('publisher:publisher_course_run_detail', kwargs={'pk': self.new_course_run.id}),
            status_code=302,
            target_status_code=200
        )

        self.new_course_run = CourseRun.objects.get(id=self.new_course_run.id)
        self.assertEqual(self.new_course_run.min_effort, self.updated_dict['min_effort'])
        self.assertEqual(self.new_course_run.max_effort, self.updated_dict['max_effort'])

    def assert_email_sent(self, object_path, subject, expected_body):
        """
        DRY method to assert sent email data.
        """
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(str(mail.outbox[0].subject), subject)

        body = mail.outbox[0].body.strip()
        self.assertIn(expected_body, body)
        page_url = 'https://{host}{path}'.format(host=self.site.domain.strip('/'), path=object_path)
        self.assertIn(page_url, body)

    def test_studio_instance_with_course_team(self):
        """
        Verify that non internal users cannot see course key field.
        """
        non_internal_user, __ = create_non_staff_user_and_login(self)
        non_internal_user.groups.add(self.organization_extension.group)
        assign_perm(
            OrganizationExtension.EDIT_COURSE_RUN, self.organization_extension.group, self.organization_extension
        )
        response = self.client.get(self.edit_page_url)
        response_content = BeautifulSoup(response.content)

        course_id_attribute = response_content.find(
            "input", {"id": "id_lms_course_id", "type": "hidden", "name": "lms_course_id"}
        )
        assert course_id_attribute is not None

        self.assertContains(response, 'Studio URL')
        self.assertContains(response, 'STUDIO URL')
        self.assertContains(response, 'Not yet created')

        self.new_course_run.lms_course_id = 'course-v1:edxTest+Test342+2016Q1'
        self.new_course_run.save()
        response = self.client.get(self.edit_page_url)
        response_content = BeautifulSoup(response.content)

        lms_course_id_attribute = response_content.find(
            "input", {"id": "id_lms_course_id", "type": "hidden", "name": "lms_course_id"}
        )
        studio_link_attribute = response_content.find("a", {"class": "studio-link"})
        assert lms_course_id_attribute is not None
        assert studio_link_attribute is not None

    def test_studio_instance_with_project_coordinator(self):
        """
        Verify that PC can see the course-key input field. And on post course-key remains in db.
        """
        pc_user = UserFactory()
        pc_user.groups.add(self.group_project_coordinator)
        pc_user.groups.add(self.organization_extension.group)

        assign_perm(
            OrganizationExtension.EDIT_COURSE_RUN, self.organization_extension.group, self.organization_extension
        )
        self.client.logout()
        self.client.login(username=pc_user.username, password=USER_PASSWORD)

        self.new_course_run.lms_course_id = 'course-v1:edxTest+Test342+2016Q1'
        self.new_course_run.save()
        response = self.client.get(self.edit_page_url)
        response_content = BeautifulSoup(response.content)

        self.assertContains(response, self.new_course_run.lms_course_id)
        lms_course_id_attribute = response_content.find(
            "input", {"id": "id_lms_course_id", "name": "lms_course_id", "class": "field-input"}
        )
        assert lms_course_id_attribute is not None

        studio_link_attribute = response_content.find("a", {"class": "studio-link"})
        assert studio_link_attribute is None

        data = {'full_description': 'This is testing description.', 'image': ''}
        updated_dict = self._post_data(data, self.new_course, None)
        self.client.post(self.edit_page_url, updated_dict)

        response = self.client.get(self.edit_page_url)
        self.assertContains(response, self.new_course_run.lms_course_id)

    def test_price_hidden_without_seat(self):
        """
        Verify that price widget appears if the seat type not audit.
        """
        self.user.groups.add(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))
        response = self.client.get(self.edit_page_url)
        self.assertNotContains(response, '<div id="seatPriceBlock" class="col col-6 hidden" style="display: block;">')

    @ddt.data(Seat.PROFESSIONAL, Seat.VERIFIED)
    def test_price_visible(self, seat_type):
        """
        Verify that price widget appear if the seat type other than audit.
        """
        self.user.groups.add(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))
        data = {'full_description': 'This is testing description.', 'image': ''}
        updated_dict = self._post_data(data, self.new_course, self.new_course_run)
        updated_dict['type'] = seat_type
        updated_dict['price'] = 10.00

        self.client.post(self.edit_page_url, updated_dict)

        response = self.client.get(self.edit_page_url)
        self.assertContains(response, '<div id="seatPriceBlock" class="col col-6')

    def test_has_about_page_info(self):
        """
        Verify that edit pages shows the about page information block
        """
        response = self.client.get(self.edit_page_url)
        self.assertContains(response, '<div id="about-page" class="course-information">')

    def test_owner_role_change_on_edit(self):
        """ Verify that when a user made changes in course run, course will be assign to him,
        and state will be changed to `Draft`. """

        self.new_course_run.course_run_state.name = CourseRunStateChoices.Review
        self.new_course_run.save()
        # check that current owner is course team
        self.assertEqual(self.new_course_run.course_run_state.owner_role, PublisherUserRole.CourseTeam)

        pc_user = self.new_course_run.course.course_user_roles.get(role=PublisherUserRole.ProjectCoordinator).user
        pc_user.groups.add(self.group_project_coordinator)
        pc_user.groups.add(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))

        assign_perm(
            OrganizationExtension.EDIT_COURSE_RUN, self.group_project_coordinator, self.organization_extension
        )
        assign_perm(
            OrganizationExtension.VIEW_COURSE_RUN, self.group_project_coordinator, self.organization_extension
        )
        self.client.logout()
        self.client.login(username=pc_user.username, password=USER_PASSWORD)

        response = self.client.get(reverse('publisher:publisher_course_run_detail', args=[self.new_course_run.id]))
        self.assertEqual(response.context['add_warning_popup'], True)
        self.assertEqual(response.context['current_team_name'], 'course team')
        self.assertEqual(response.context['team_name'], 'project coordinator')

        response = self.client.post(self.edit_page_url, self.updated_dict)

        self.assertRedirects(
            response,
            expected_url=reverse('publisher:publisher_course_run_detail', kwargs={'pk': self.new_course_run.id}),
            status_code=302,
            target_status_code=200
        )

        course_run_state = CourseRunState.objects.get(id=self.new_course_run.course_run_state.id)
        self.assertEqual(course_run_state.name, CourseRunStateChoices.Draft)
        self.assertEqual(course_run_state.owner_role, PublisherUserRole.ProjectCoordinator)

    def test_course_key_not_getting_blanked(self):
        """
        Verify that `lms_course_id` notest_course_run_detail_page_stafft getting blanked if course
        team updates with empty value.
        """
        self.client.logout()
        user = self.new_course.course_team_admin
        self.client.login(username=user.username, password=USER_PASSWORD)

        post_data = self._post_data({'image': ''}, self.new_course, self.new_course_run, self.seat)
        lms_course_id = 'course-v1:edX+DemoX+Demo_Course'
        self.new_course_run.lms_course_id = lms_course_id
        self.new_course_run.save()

        # Verify that post data has empty value for `lms_course_id`
        self.assertEqual(post_data['lms_course_id'], '')

        response = self.client.post(self.edit_page_url, post_data)

        self.assertRedirects(
            response,
            expected_url=reverse('publisher:publisher_course_run_detail', kwargs={'pk': self.new_course_run.id}),
            status_code=302,
            target_status_code=200
        )

        self.new_course_run = CourseRun.objects.get(id=self.new_course_run.id)
        # Verify that `lms_course_id` not wiped.
        self.assertEqual(self.new_course_run.lms_course_id, lms_course_id)

    def test_published_course_run_editing_not_change_state_and_ownership(self):
        """ Verify that when a user made changes in published course run, course-run state remains
         same and owner ship as well."""

        factories.CourseUserRoleFactory.create(course=self.course, role=PublisherUserRole.CourseTeam, user=self.user)

        factories.CourseUserRoleFactory(
            course=self.new_course_run.course, role=PublisherUserRole.Publisher, user=UserFactory()
        )

        self.new_course_run.course_run_state.name = CourseRunStateChoices.Published
        self.new_course_run.course_run_state.preview_accepted = True
        self.new_course_run.course_run_state.owner_role = PublisherUserRole.Publisher
        self.new_course_run.course_run_state.save()

        lms_course_id = 'course-v1:edX+DemoX+Demo_Course'
        self.new_course_run.lms_course_id = lms_course_id
        self.new_course_run.save()

        self.updated_dict['min_effort'] = 2
        self.updated_dict['max_effort'] = 51

        response = self.client.post(self.edit_page_url, self.updated_dict)

        self.assertRedirects(
            response,
            expected_url=reverse('publisher:publisher_course_run_detail', kwargs={'pk': self.new_course_run.id}),
            status_code=302,
            target_status_code=200
        )

        self.assertEqual(self.new_course_run.course_run_state.name, CourseRunStateChoices.Published)
        self.assertEqual(self.new_course_run.course_run_state.owner_role, PublisherUserRole.Publisher)

        course_key = CourseKey.from_string(self.new_course_run.lms_course_id)

        # email send after editing.
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual([self.new_course_run.course.publisher.email], mail.outbox[0].to)

        expected_subject = 'Changes to published course run: {title} {run_number}'.format(
            title=self.new_course_run.course.title,
            run_number=course_key.run
        )
        self.assertEqual(str(mail.outbox[0].subject), expected_subject)

    def test_external_key_visible_canonical_course_run(self):
        """
        Verify that the external key field is visible when the course_metadata version of the course run
        is the canonical course run and the course_metadata course run has a Masters seat
        """
        masters_program_type = DiscoveryProgramType.objects.get(slug='masters')
        discovery_program = ProgramFactory(type=masters_program_type)
        discovery_curriculum = CurriculumFactory(program=discovery_program)
        course_key = self.new_course.organizations.first().key + '+' + self.new_course.number
        discovery_course = CourseFactory(partner=self.partner, key=course_key)
        CurriculumCourseMembershipFactory(
            course=discovery_course,
            curriculum=discovery_curriculum
        )

        discovery_course.canonical_course_run = CourseRunFactory(course=discovery_course)
        discovery_course.save()
        masters_seat_type = SeatTypeFactory.masters()
        discovery_course.canonical_course_run.seats.add(SeatFactory(type=masters_seat_type))
        discovery_course.canonical_course_run.save()

        self.new_course_run.lms_course_id = discovery_course.canonical_course_run.key
        self.new_course_run.save()

        response = self.client.get(self.edit_page_url)
        self.assertContains(response, '<div class="field-title" id="institution-course-id">')

    @ddt.data(True, False)
    def test_external_key_visible_publisher_run_has_masters(self, masters_track):
        """
        Verify that the external key field is visible when the publisher course run has a seat
        with masters_track and is not visible if no seats have a masters_track.
        """
        masters_program_type = DiscoveryProgramType.objects.get(slug='masters')
        discovery_program = ProgramFactory(type=masters_program_type)
        discovery_curriculum = CurriculumFactory(program=discovery_program)
        course_key = self.new_course.organizations.first().key + '+' + self.new_course.number
        discovery_course = CourseFactory(partner=self.partner, key=course_key)
        CurriculumCourseMembershipFactory(
            course=discovery_course,
            curriculum=discovery_curriculum
        )

        factories.SeatFactory(course_run=self.new_course_run, masters_track=masters_track)

        response = self.client.get(self.edit_page_url)
        if masters_track:
            self.assertContains(response, '<div class="field-title" id="institution-course-id">')
        else:
            self.assertNotContains(response, '<div class="field-title" id="institution-course-id">')

    def test_external_key_not_visible_course_not_in_masters(self):
        """
        Verify that the external key field is not visible when the discovery course is not in a masters program.
        """
        course_key = self.new_course.organizations.first().key + '+' + self.new_course.number
        # This creates a discovery course which is necessary to test external key
        CourseFactory(key=course_key)

        response = self.client.get(self.edit_page_url)
        self.assertNotContains(response, '<div class="field-title" id="institution-course-id">')


class CourseRevisionViewTests(SiteMixin, TestCase):
    """ Tests for CourseReview"""

    def setUp(self):
        super(CourseRevisionViewTests, self).setUp()
        self.course = factories.CourseFactory()

        self.user = UserFactory()
        self.client.login(username=self.user.username, password=USER_PASSWORD)

    def test_get_revision(self):
        """
        Verify that view return history_object against given revision_id.
        """
        self.course.title = 'Updated title'
        self.course.save()

        # index 0 will return the latest object
        revision_id = self.course.history.all()[1].history_id
        response = self._get_response(course_id=self.course.id, revision_id=revision_id)
        history_object = response.context['history_object']

        self.assertIn('history_object', response.context)
        self.assertNotEqual(self.course.title, history_object.title)

    def test_get_with_invalid_revision_id(self):
        """
        Verify that view returns 404 response if revision id does not found.
        """
        response = self._get_response(course_id=self.course.id, revision_id='0000')
        self.assertEqual(response.status_code, 404)

    def test_get_with_invalid_course_id(self):
        """
        Verify that view returns 404 response if course id does not found.
        """
        self.course.title = 'Updated title'
        self.course.save()

        # index 0 will return the latest object
        revision_id = self.course.history.all()[1].history_id
        response = self._get_response(course_id='0000', revision_id=revision_id)
        self.assertEqual(response.status_code, 404)

    def _get_response(self, course_id, revision_id):
        """ Return the response object with given revision_id. """
        revision_path = reverse('publisher:publisher_course_revision',
                                kwargs={'pk': course_id, 'revision_id': revision_id})

        return self.client.get(path=revision_path)


@ddt.ddt
class CreateRunFromDashboardViewTests(SiteMixin, TestCase):
    """ Tests for the publisher `CreateRunFromDashboardView`. """

    def setUp(self):
        super(CreateRunFromDashboardViewTests, self).setUp()
        self.user = UserFactory()
        self.organization_extension = factories.OrganizationExtensionFactory()

        self.course = factories.CourseFactory(organizations=[self.organization_extension.organization])
        self.course.version = Course.SEAT_VERSION
        self.course.save()

        factories.CourseStateFactory(course=self.course)
        factories.CourseUserRoleFactory.create(course=self.course, role=PublisherUserRole.CourseTeam, user=self.user)
        factories.CourseUserRoleFactory.create(course=self.course, role=PublisherUserRole.Publisher, user=UserFactory())
        factories.CourseUserRoleFactory.create(
            course=self.course, role=PublisherUserRole.ProjectCoordinator, user=UserFactory()
        )
        factories.CourseUserRoleFactory.create(
            course=self.course, role=PublisherUserRole.MarketingReviewer, user=UserFactory()
        )

        self.user.groups.add(self.organization_extension.group)

        assign_perm(
            OrganizationExtension.VIEW_COURSE_RUN, self.organization_extension.group, self.organization_extension
        )
        assign_perm(OrganizationExtension.VIEW_COURSE, self.organization_extension.group, self.organization_extension)

        self.client.login(username=self.user.username, password=USER_PASSWORD)

        self.create_course_run_url = reverse('publisher:publisher_create_run_from_dashboard')

    def test_courserun_form_without_login(self):
        """ Verify that user can't access new course run form page when not logged in. """
        self.client.logout()
        response = self.client.get(self.create_course_run_url)

        self.assertRedirects(
            response,
            expected_url='{url}?next={next}'.format(
                url=reverse('login'),
                next=self.create_course_run_url
            ),
            status_code=302,
            target_status_code=302
        )

        self.client.login(username=self.user.username, password=USER_PASSWORD)

        response = self.client.get(self.create_course_run_url)

        self.assertEqual(response.status_code, 200)

    def _post_data(self):
        current_datetime = datetime.now(timezone('US/Central'))
        return {
            'course': self.course.id,
            'start': (current_datetime + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S'),
            'end': (current_datetime + timedelta(days=60)).strftime('%Y-%m-%d %H:%M:%S'),
            'pacing_type': 'self_paced',
            'type': Seat.VERIFIED,
            'price': 450
        }

    def test_create_course_run_and_seat_without_parent_course(self):
        """ Verify that user cannot create course run without selecting parent course.
        """
        post_data = self._post_data()
        post_data.pop('course')
        response = self.client.post(self.create_course_run_url, post_data)
        self.assertContains(response, 'The page could not be updated. Make', status_code=400)

    def test_create_course_run_without_access_to_course(self):
        """ Verify that user cannot create course run for a course they don't have access to.
        """
        self.course.organizations.clear()  # user will no longer be associated with course
        post_data = self._post_data()
        response = self.client.post(self.create_course_run_url, post_data)
        self.assertContains(response, 'The page could not be updated. Make', status_code=400)

    def test_courserun_form_includes_seat_fields_on_error_for_non_entitlement_course(self):
        """ Verify that the Seat fields are visible when error occurs for Courses that do not use entitlements. """
        self.course.version = Course.SEAT_VERSION
        self.course.save()

        post_data = {'course': self.course.id}
        response = self.client.post(self.create_course_run_url, post_data)
        self.assertContains(response, '<div class="layout-full layout js-seat-form">', status_code=400)

    def test_courserun_form_does_not_include_seat_fields_on_error_for_entitlement_course(self):
        """ Verify that the Seat fields are hidden when error occurs for Courses that use entitlements. """
        self.course.version = Course.ENTITLEMENT_VERSION
        self.course.save()

        post_data = {'course': self.course.id}
        response = self.client.post(self.create_course_run_url, post_data)
        self.assertContains(response, '<div class="layout-full layout js-seat-form hidden">', status_code=400)

    @ddt.data(
        (CourseEntitlement.PROFESSIONAL, 1, [{'type': Seat.PROFESSIONAL, 'price': 1}]),
        (CourseEntitlement.VERIFIED, 1, [{'type': Seat.VERIFIED, 'price': 1}, {'type': Seat.AUDIT, 'price': 0}]),
    )
    @ddt.unpack
    def test_create_run_for_entitlement_course(self, entitlement_mode, entitlement_price, expected_seats):
        """
        Verify that when creating a run for a Course that uses entitlements, Seats are created from the
        entitlement data associated with the parent course.
        """
        self.course.version = Course.ENTITLEMENT_VERSION
        self.course.save()
        assign_perm(
            OrganizationExtension.VIEW_COURSE_RUN, self.organization_extension.group, self.organization_extension
        )

        self.course.entitlements.create(mode=entitlement_mode, price=entitlement_price)
        post_data = {
            'start': '2018-02-01 00:00:00',
            'end': '2018-02-28 00:00:00',
            'pacing_type': 'instructor_paced',
            'course': self.course.id
        }

        num_courseruns_before = self.course.course_runs.count()
        response = self.client.post(self.create_course_run_url, post_data)
        num_courseruns_after = self.course.course_runs.count()
        self.assertGreater(num_courseruns_after, num_courseruns_before)

        new_courserun = self.course.course_runs.latest('created')
        self.assertEqual(new_courserun.start_date_temporary.strftime('%Y-%m-%d %H:%M:%S'), post_data['start'])
        self.assertEqual(new_courserun.end_date_temporary.strftime('%Y-%m-%d %H:%M:%S'), post_data['end'])
        self.assertEqual(new_courserun.pacing_type_temporary, post_data['pacing_type'])

        self.assertRedirects(
            response,
            expected_url=reverse('publisher:publisher_course_run_detail', kwargs={'pk': new_courserun.id}),
            status_code=302,
            target_status_code=200
        )

        self.assertEqual(new_courserun.seats.count(), len(expected_seats))
        for expected_seat in expected_seats:
            actual_seat = new_courserun.seats.get(type=expected_seat['type'])
            self.assertEqual(expected_seat['type'], actual_seat.type)
            self.assertEqual(expected_seat['price'], actual_seat.price)

    def test_create_run_for_misconfigured_entitlement_course(self):
        """
        Verify that a user cannot create a new course run for a Course that has been configured to use entitlements
        but does not have exactly one entitlement.
        """
        self.course.version = Course.ENTITLEMENT_VERSION
        self.course.save()
        assign_perm(
            OrganizationExtension.VIEW_COURSE_RUN, self.organization_extension.group, self.organization_extension
        )
        post_data = {
            'start': '2018-02-01 00:00:00',
            'end': '2018-02-28 00:00:00',
            'pacing_type': 'instructor_paced',
            'course': self.course.id
        }

        self.assertEqual(self.course.entitlements.count(), 0)
        num_courseruns_before = self.course.course_runs.count()

        response = self.client.post(self.create_course_run_url, post_data)
        num_courseruns_after = self.course.course_runs.count()
        self.assertEqual(num_courseruns_before, num_courseruns_after)
        self.assertContains(response, 'The certificate configuration for this course is incorrect', status_code=400)

        self.course.entitlements.create(mode=CourseEntitlement.VERIFIED, price=1)
        self.course.entitlements.create(mode=CourseEntitlement.PROFESSIONAL, price=1)
        self.assertEqual(self.course.entitlements.count(), 2)

        response = self.client.post(self.create_course_run_url, post_data)
        num_courseruns_after = self.course.course_runs.count()
        self.assertEqual(num_courseruns_before, num_courseruns_after)
        self.assertContains(response, 'The certificate configuration for this course is incorrect', status_code=400)

    def test_create_run_for_non_usd_entitlement_course(self):
        """
        Verify that a user cannot create a new course run for a Course that has been configured to use entitlements
        with a currency other than USD.
        """
        self.course.version = Course.ENTITLEMENT_VERSION
        self.course.save()
        assign_perm(
            OrganizationExtension.VIEW_COURSE_RUN, self.organization_extension.group, self.organization_extension
        )
        post_data = {
            'start': '2018-02-01 00:00:00',
            'end': '2018-02-28 00:00:00',
            'pacing_type': 'instructor_paced',
            'course': self.course.id
        }
        self.course.entitlements.create(
            mode=CourseEntitlement.VERIFIED,
            price=100,
            currency=Currency.objects.get(code='JPY')
        )
        num_courseruns_before = self.course.course_runs.count()

        response = self.client.post(self.create_course_run_url, post_data)
        num_courseruns_after = self.course.course_runs.count()
        self.assertEqual(num_courseruns_before, num_courseruns_after)
        self.assertContains(response, 'The certificate configuration for this course is incorrect', status_code=400)

    def test_create_run_for_entitlement_course_with_seat_data_in_form(self):
        """
        Verify that a user cannot submit Seat data with the form when creating a new course run for a Course that has
        been configured to use entitlements.
        """
        self.course.version = Course.ENTITLEMENT_VERSION
        self.course.save()
        assign_perm(
            OrganizationExtension.VIEW_COURSE_RUN, self.organization_extension.group, self.organization_extension
        )
        post_data = {
            'start': '2018-02-01 00:00:00',
            'end': '2018-02-28 00:00:00',
            'pacing_type': 'instructor_paced',
            'course': self.course.id,
            'type': Seat.VERIFIED,
            'price': 2
        }

        self.course.entitlements.create(mode=CourseEntitlement.PROFESSIONAL, price=1)
        num_courseruns_before = self.course.course_runs.count()
        response = self.client.post(self.create_course_run_url, post_data)
        num_courseruns_after = self.course.course_runs.count()
        self.assertEqual(num_courseruns_before, num_courseruns_after)
        self.assertContains(response, 'The page could not be updated.', status_code=400)


@ddt.ddt
class CreateAdminImportCourseTest(SiteMixin, TestCase):
    """ Tests for the publisher `CreateAdminImportCourse`. """

    def setUp(self):
        super(CreateAdminImportCourseTest, self).setUp()
        self.user = UserFactory()

        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.page_url = reverse('publisher:publisher_admin_import_course')

        self.course = CourseFactory()

    def test_page_without_login(self):
        """ Verify that user can't access page and is correctly redirected when not logged in. """
        self.client.logout()
        response = self.client.get(self.page_url)

        self.assertRedirects(
            response,
            expected_url='{url}?next={next}'.format(
                url=reverse('login'),
                next=self.page_url
            ),
            status_code=302,
            target_status_code=302
        )

    def test_page_without_superuser(self):
        """ Verify that user can't access page when not logged in. """
        response = self.client.get(self.page_url)
        self.assertEqual(response.status_code, 404)

    def test_page_with_superuser(self):
        """ Verify that user can access page as a super user. """
        response = self._make_users_valid()
        self.assertEqual(response.status_code, 200)

    @ddt.data(
        (
            {'is_superuser': True, 'status_code': 200}
        ),
        (
            {'is_superuser': False, 'status_code': 404}
        ),
    )
    def test_page_with_post(self, post_transaction):
        """ Verify page shows message with successful import.
            Test Cases: Super User, non Super User.
        """

        # organization should be available for import
        self.course.authoring_organizations.add(OrganizationFactory())

        self._make_users_valid(post_transaction['is_superuser'])
        post_data = {'start_id': self.course.pk}
        response = self.client.post(self.page_url, post_data)
        self.assertEqual(response.status_code, post_transaction['status_code'])
        if response.status_code == 200:
            self.assertContains(response, 'Course Imported')

    def test_page_with_invalid_course_id(self):
        """ Verify page shows error message if import fails. """
        self._make_users_valid()
        post_data = {'start_id': 100}
        response = self.client.post(self.page_url, post_data)
        self.assertContains(response, 'Course matching query does not exist.')

    def test_import_with_failure(self):
        """ Verify page shows error in case of any error. """
        self._make_users_valid()
        post_data = {'start_id': self.course.pk}
        response = self.client.post(self.page_url, post_data)
        self.assertContains(response, 'Some error occurred')

    def test_course_user_roles_creation(self):
        """ Verify course add the course-users roles after importing the course. """
        # organization should be available for import
        organization = OrganizationFactory()
        self.course.authoring_organizations.add(organization)
        self._add_org_roles(organization)
        self._make_users_valid()

        post_data = {'start_id': self.course.pk}
        response = self.client.post(self.page_url, post_data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Course Imported')

        default_roles = [
            PublisherUserRole.MarketingReviewer, PublisherUserRole.ProjectCoordinator, PublisherUserRole.Publisher
        ]
        publisher_course = Course.objects.get(course_metadata_pk=self.course.pk)
        expected_count = publisher_course.course_user_roles.filter(role__in=default_roles).count()
        self.assertEqual(len(default_roles), expected_count)

    def test_course_user_roles_without_organization_extension(self):
        """ Verify that course import works fine even without org extension. """

        # organization should be available for import
        organization = OrganizationFactory()
        self.course.authoring_organizations.add(organization)
        self._make_users_valid()

        post_data = {'start_id': self.course.pk}
        response = self.client.post(self.page_url, post_data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Course Imported')

    def _make_users_valid(self, is_superuser=True):
        """ make user eligible for the page."""
        self.client.logout()
        self.user.is_superuser = is_superuser
        self.user.save()

        self.client.login(username=self.user.username, password=USER_PASSWORD)
        return self.client.get(self.page_url)

    def _add_org_roles(self, organization):
        """ Create default roles for the organization """

        organization_extension = factories.OrganizationExtensionFactory(organization=organization)
        self.user.groups.add(organization_extension.group)

        factories.OrganizationUserRoleFactory(
            organization=organization_extension.organization, role=PublisherUserRole.MarketingReviewer
        )
        factories.OrganizationUserRoleFactory(
            organization=organization_extension.organization, role=PublisherUserRole.ProjectCoordinator
        )
        factories.OrganizationUserRoleFactory(
            organization=organization_extension.organization, role=PublisherUserRole.Publisher
        )
