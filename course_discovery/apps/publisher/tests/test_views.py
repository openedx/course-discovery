# pylint: disable=no-member
import json
from datetime import datetime, timedelta

import ddt
import factory
from bs4 import BeautifulSoup
from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.sites.models import Site
from django.core import mail
from django.db import IntegrityError
from django.forms import model_to_dict
from django.test import TestCase
from django.urls import reverse
from guardian.shortcuts import assign_perm
from mock import patch
from opaque_keys.edx.keys import CourseKey
from pytz import timezone
from testfixtures import LogCapture

from course_discovery.apps.core.models import User
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.core.tests.helpers import make_image_file
from course_discovery.apps.course_metadata.tests import toggle_switch
from course_discovery.apps.course_metadata.tests.factories import CourseFactory, OrganizationFactory, PersonFactory
from course_discovery.apps.ietf_language_tags.models import LanguageTag
from course_discovery.apps.publisher.choices import (CourseRunStateChoices, CourseStateChoices, InternalUserRole,
                                                     PublisherUserRole)
from course_discovery.apps.publisher.constants import (ADMIN_GROUP_NAME, INTERNAL_USER_GROUP_NAME,
                                                       PROJECT_COORDINATOR_GROUP_NAME, REVIEWER_GROUP_NAME)
from course_discovery.apps.publisher.models import (Course, CourseRun, CourseRunState, CourseState,
                                                    OrganizationExtension, Seat)
from course_discovery.apps.publisher.tests import factories
from course_discovery.apps.publisher.tests.utils import create_non_staff_user_and_login
from course_discovery.apps.publisher.utils import is_email_notification_enabled
from course_discovery.apps.publisher.views import logger as publisher_views_logger
from course_discovery.apps.publisher.views import CourseRunDetailView, get_course_role_widgets_data
from course_discovery.apps.publisher.wrappers import CourseRunWrapper
from course_discovery.apps.publisher_comments.models import CommentTypeChoices
from course_discovery.apps.publisher_comments.tests.factories import CommentFactory


@ddt.ddt
class CreateCourseViewTests(TestCase):
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

        # create base course object
        self.course = factories.CourseFactory()

        self.course.organizations.add(self.organization_extension.organization)
        self.site = Site.objects.get(pk=settings.SITE_ID)
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

    def test_create_course(self):
        """
        Verify that user can create course successfully.
        """
        data = {'title': 'Test2', 'number': 'testX453', 'image': make_image_file('test_banner.jpg')}
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
    )
    def test_create_course_invalid_image(self, image):
        """
        Verify that a new course with an invalid image shows the proper error.
        """
        image_error = [
            'The image you uploaded is of incorrect resolution. Course image files must be 2120 x 1192 pixels in size.'
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
        with patch.object(Course, "save") as mock_method:
            mock_method.side_effect = IntegrityError
            response = self.client.post(reverse('publisher:publisher_courses_new'), course_dict, files=data['image'])

        self.assertEqual(response.status_code, 400)
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
        data = {'title': 'Test2', 'number': 'testX234', 'image': '', 'add_new_run': True}
        course_dict = self._post_data(data, self.course)
        response = self.client.post(reverse('publisher:publisher_courses_new'), course_dict)

        course = Course.objects.get(number=course_dict['number'])

        self.assertRedirects(
            response,
            expected_url=reverse('publisher:publisher_course_runs_new', kwargs={'parent_course_id': course.id}),
            status_code=302,
            target_status_code=200
        )


class CreateCourseRunViewTests(TestCase):
    """ Tests for the publisher `UpdateCourseRunView`. """

    def setUp(self):
        super(CreateCourseRunViewTests, self).setUp()
        self.user = UserFactory()
        self.course_run = factories.CourseRunFactory()
        self.course = self.course_run.course
        factories.CourseStateFactory(course=self.course)
        factories.CourseUserRoleFactory.create(course=self.course, role=PublisherUserRole.CourseTeam, user=self.user)
        factories.CourseUserRoleFactory.create(course=self.course, role=PublisherUserRole.Publisher, user=UserFactory())
        factories.CourseUserRoleFactory.create(
            course=self.course, role=PublisherUserRole.ProjectCoordinator, user=UserFactory()
        )
        factories.CourseUserRoleFactory.create(
            course=self.course, role=PublisherUserRole.MarketingReviewer, user=UserFactory()
        )
        self.organization_extension = factories.OrganizationExtensionFactory()
        self.course.organizations.add(self.organization_extension.organization)
        self.user.groups.add(self.organization_extension.group)

        self.course_run_dict = model_to_dict(self.course_run)
        self.course_run_dict.update({'is_self_paced': True})
        self._pop_valuse_from_dict(
            self.course_run_dict,
            ['end', 'enrollment_start', 'enrollment_end', 'priority', 'certificate_generation', 'id']
        )
        current_datetime = datetime.now(timezone('US/Central'))
        self.course_run_dict['start'] = (current_datetime + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
        self.course_run_dict['end'] = (current_datetime + timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S')
        self.site = Site.objects.get(pk=settings.SITE_ID)
        self.client.login(username=self.user.username, password=USER_PASSWORD)

    def _pop_valuse_from_dict(self, data_dict, key_list):
        for key in key_list:
            data_dict.pop(key)

    def test_courserun_form_with_login(self):
        """ Verify that user can access new course run form page when logged in. """
        response = self.client.get(
            reverse('publisher:publisher_course_runs_new', kwargs={'parent_course_id': self.course.id})
        )

        self.assertEqual(response.status_code, 200)

    def test_courserun_form_without_login(self):
        """ Verify that user can't access new course run form page when not logged in. """
        self.client.logout()
        response = self.client.get(
            reverse('publisher:publisher_course_runs_new', kwargs={'parent_course_id': self.course.id})
        )

        self.assertRedirects(
            response,
            expected_url='{url}?next={next}'.format(
                url=reverse('login'),
                next=reverse('publisher:publisher_course_runs_new', kwargs={'parent_course_id': self.course.id})
            ),
            status_code=302,
            target_status_code=302
        )

        self.client.login(username=self.user.username, password=USER_PASSWORD)

        response = self.client.get(
            reverse('publisher:publisher_course_runs_new', kwargs={'parent_course_id': self.course.id})
        )

        self.assertEqual(response.status_code, 200)

    def test_create_course_run_and_seat_with_errors(self):
        """ Verify that without providing required data course run cannot be
        created.
        """
        post_data = self.course_run_dict
        post_data.update(factory.build(dict, FACTORY_CLASS=factories.SeatFactory))
        self._pop_valuse_from_dict(
            post_data, ['upgrade_deadline', 'start']
        )

        response = self.client.post(
            reverse('publisher:publisher_course_runs_new', kwargs={'parent_course_id': self.course.id}),
            post_data
        )
        self.assertEqual(response.status_code, 400)

        with patch('django.forms.models.BaseModelForm.is_valid') as mocked_is_valid:
            mocked_is_valid.return_value = True
            with LogCapture(publisher_views_logger.name) as log_capture:
                response = self.client.post(
                    reverse('publisher:publisher_course_runs_new', kwargs={'parent_course_id': self.course.id}),
                    post_data
                )

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
        response = self.client.post(
            reverse('publisher:publisher_course_runs_new', kwargs={'parent_course_id': self.course.id}),
            post_data
        )

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
        response = self.client.post(
            reverse('publisher:publisher_course_runs_new', kwargs={'parent_course_id': self.course.id}),
            post_data
        )

        self.assertContains(response, 'Only audit seat can be without price.', status_code=400)

        post_data['price'] = 450

        response = self.client.post(
            reverse('publisher:publisher_course_runs_new', kwargs={'parent_course_id': self.course.id}),
            post_data
        )

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
        """
        latest_run = self.course.course_runs.latest('created')
        factories.SeatFactory(course_run=latest_run, type=Seat.VERIFIED, price=550.0)
        latest_seat = latest_run.seats.latest('created')
        response = self.client.get(
            reverse('publisher:publisher_course_runs_new', kwargs={'parent_course_id': self.course.id})
        )
        response_content = BeautifulSoup(response.content)

        pacing_type_attribute = response_content.find(
            "input", {"value": latest_run.pacing_type, "type": "radio", "name": "pacing_type"}
        )
        seat_type_attribute = response_content.find("option", {"value": latest_seat.type})
        price_attribute = response_content.find(
            "input", {"value": latest_seat.price, "id": "id_price", "step": "0.01", "type": "number"}
        )

        # Verify that existing course run and seat values auto populated on form.
        assert pacing_type_attribute is not None
        assert seat_type_attribute is not None
        assert price_attribute is not None

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
        response = self.client.post(
            reverse('publisher:publisher_course_runs_new', kwargs={'parent_course_id': self.course.id}),
            post_data
        )

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
        response = self.client.post(
            reverse('publisher:publisher_course_runs_new', kwargs={'parent_course_id': self.course.id}),
            post_data
        )

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

    def test_canot_create_course_run_without_roles(self):
        """
        Verify that user can create a new course run with credit seat.
        """
        course = factories.CourseFactory()
        organization_extension = factories.OrganizationExtensionFactory()
        course.organizations.add(organization_extension.organization)
        self.user.groups.add(organization_extension.group)

        response = self.client.post(
            reverse('publisher:publisher_course_runs_new', kwargs={'parent_course_id': course.id}),
            {}
        )

        self.assertContains(response, 'Your organization does not have default roles', status_code=400)


@ddt.ddt
class CourseRunDetailTests(TestCase):
    """ Tests for the course-run detail view. """

    def setUp(self):
        super(CourseRunDetailTests, self).setUp()
        self.course = factories.CourseFactory()
        self.user = UserFactory()
        self.user.groups.add(Group.objects.get(name=ADMIN_GROUP_NAME))
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.course_run = factories.CourseRunFactory(course=self.course)
        self.course_run.lms_course_id = 'course-v1:edX+DemoX+Demo_Course'
        self.course_run.save()

        self.organization_extension = factories.OrganizationExtensionFactory()
        self.course.organizations.add(self.organization_extension.organization)

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
        self.course_run.staff.add(PersonFactory(profile_url='http://test-profile'))

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
        """ Verify that user can access detail page without any data
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
        """ Verify that detail page contains all the data for drupal, studio and
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
            'Course Name', 'Organization', 'Number', 'Start Date', 'End Date',
            'Enrollment Start Date', 'Enrollment End Date', 'Pacing Type'
        ]
        for field in fields:
            self.assertContains(response, field)

        values = [
            self.wrapped_course_run.title, self.wrapped_course_run.number,
            self.course_run.pacing_type
        ]
        for value in values:
            self.assertContains(response, value)

        self._assert_dates(response)

    def _assert_drupal(self, response):
        """ Helper method to test drupal values and labels. """
        fields = [
            'Title', 'Number', 'Course ID', 'Price', 'Subtitle', 'Organization', 'Subject', 'XSeries',
            'Start Date (time in UTC)', 'End Date (time in UTC)', 'Self Paced', 'Staff', 'Estimated Effort',
            'Languages', 'Video Transcript Languages', 'Level', 'Full Description', "What You'll Learn",
            'Keywords', 'Sponsors', 'Enrollment Types', 'Learner Testimonials', 'FAQ', 'Course About Video'
        ]
        for field in fields:
            self.assertContains(response, field)

        values = [
            self.wrapped_course_run.title, self.wrapped_course_run.lms_course_id,
            self.wrapped_course_run.seat_price,
            self.wrapped_course_run.min_effort,
            self.wrapped_course_run.pacing_type, self.wrapped_course_run.persons,
            self.wrapped_course_run.max_effort, self.wrapped_course_run.language.name,
            self.wrapped_course_run.transcript_languages, self.wrapped_course_run.level_type,
            self.wrapped_course_run.expected_learnings, self.wrapped_course_run.course.learner_testimonial,
            self.wrapped_course_run.course.faq, self.wrapped_course_run.course.video_link
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
        for value in [self.course_run.start,
                      self.course_run.end,
                      self.course_run.enrollment_start,
                      self.course_run.enrollment_end]:
            self.assertContains(response, value.strftime(self.date_format))

    def test_detail_page_with_comments(self):
        """ Verify that detail page contains all the data along with comments
        for course.
        """
        self.client.logout()
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        site = Site.objects.get(pk=settings.SITE_ID)

        comment = CommentFactory(content_object=self.course_run, user=self.user, site=site)
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
            user=self.user, site=site, comment_type=CommentTypeChoices.Decline_Preview
        )
        response = self.client.get(self.page_url)
        self.assertContains(response, decline_comment.comment)
        self.assertContains(response, '<b>Preview Decline:</b>')

    def test_get_course_return_none(self):
        """ Verify that `PublisherPermissionMixin.get_course` return none
        if `publisher_object` doesn't have `course` attr.
        """
        non_staff_user, group = create_non_staff_user_and_login(self)   # pylint: disable=unused-variable
        page_url = reverse('publisher:publisher_course_run_detail', args=[self.course_run.id])
        with patch.object(CourseRunDetailView, 'get_object', return_value=non_staff_user):
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
        self.assertContains(response, '<a href="{url}">{slug}</a>'.format(url=page_url, slug=course_run.course.title))
        self.assertContains(response, '<li class="breadcrumb-item active">')
        self.assertContains(
            response, '{type}: {start}'.format(
                type=course_run.get_pacing_type_display(),
                start=course_run.start.strftime("%B %d, %Y")
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

    def test_comments_with_enable_switch(self):
        """ Verify that user will see the comments widget when
        'publisher_comment_widget_feature' is enabled.
        """
        toggle_switch('publisher_comment_widget_feature', True)
        response = self.client.get(self.page_url)

        self.assertContains(response, '<div id="comments-widget" class="comment-container ">')

    def test_comments_with_disable_switch(self):
        """ Verify that user will not see the comments widget when
        'publisher_comment_widget_feature' is disable.
        """
        toggle_switch('publisher_comment_widget_feature', False)
        response = self.client.get(self.page_url)
        self.assertContains(response, '<div id="comments-widget" class="comment-container hidden">')

    def test_approval_widget_with_enable_switch(self):
        """ Verify that user will see the history widget when
        'publisher_approval_widget_feature' is enabled.
        """
        self.user.groups.add(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))
        toggle_switch('publisher_approval_widget_feature', True)
        response = self.client.get(self.page_url)
        self.assertContains(response, '<div id="approval-widget" class="approval-widget ">')

    def test_approval_widget_with_disable_switch(self):
        """ Verify that user will not see the history widget when
        'publisher_approval_widget_feature' is disabled.
        """
        self.user.groups.add(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))
        toggle_switch('publisher_approval_widget_feature', False)
        response = self.client.get(self.page_url)
        self.assertContains(response, '<div id="approval-widget" class="approval-widget hidden">')

    def test_course_run_approval_widget_for_course_team(self):
        """
        Verify that user can see approval widget on course detail page with `Send for Review` button.
        """
        toggle_switch('publisher_approval_widget_feature', True)
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
        toggle_switch('publisher_approval_widget_feature', True)

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
        toggle_switch('publisher_approval_widget_feature', True)
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
        self.course_run.preview_url = None
        self.course_run.save()

        response = self.client.get(self.page_url)
        self.assertContains(response, 'ABOUT PAGE PREVIEW')
        self.assertContains(
            response,
            '<button data-url="{url}" class="btn btn-neutral btn-save-preview-url">'.format(url=preview_api_url)
        )
        self.assertContains(response, '<input id="id-review-url" type="text">')

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
class DashboardTests(TestCase):
    """ Tests for the `Dashboard`. """

    def setUp(self):
        super(DashboardTests, self).setUp()

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

        # mark course as in in preview
        self.course_run_2.preview_url = 'http://'
        self.course_run_2.save()

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
        course_run_state = factories.CourseRunStateFactory(name=state, owner_role=role)
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
            studio_count=0, published_count=0, progress_count=0, preview_count=0, queries_executed=11
        )
        self._assert_tabs_with_roles(response)

    @ddt.data('progress', 'preview', 'studio', 'published')
    def test_with_internal_group(self, tab):
        """ Verify that internal user can see courses assigned to the groups. """
        response = self.assert_dashboard_response(
            studio_count=2, published_count=1, progress_count=2, preview_count=1, queries_executed=23
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
            studio_count=0, published_count=0, progress_count=0, preview_count=0, queries_executed=11
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
            studio_count=0, published_count=0, progress_count=2, preview_count=1, queries_executed=21
        )
        self._assert_tabs_with_roles(response)

    def test_studio_request_course_runs_as_pc(self):
        """ Verify that PC user can see only those courses on which he is assigned as PC role. """
        response = self.assert_dashboard_response(
            studio_count=2, published_count=1, progress_count=2, preview_count=1, queries_executed=23
        )
        self._assert_tabs_with_roles(response)

    def test_studio_request_course_runs_without_pc_group(self):
        """ Verify that PC user can see only those courses on which he is assigned as PC role. """
        self.user1.groups.remove(self.group_project_coordinator)
        response = self.assert_dashboard_response(
            studio_count=0, published_count=1, progress_count=2, preview_count=1, queries_executed=20
        )
        self._assert_tabs_with_roles(response)

    def test_without_studio_request_course_runs(self):
        """ Verify that studio tab indicates a message if no course-run available. """
        self.course_run_1.lms_course_id = 'test-1'
        self.course_run_1.save()
        self.course_run_2.lms_course_id = 'test-2'
        self.course_run_2.save()
        response = self.assert_dashboard_response(
            studio_count=0, published_count=1, progress_count=2, preview_count=1, queries_executed=21
        )
        self.assertContains(response, 'No courses are currently ready for a Studio URL.')

    def test_without_published_course_runs(self):
        """ Verify that published tab indicates a message if no course-run available. """
        self.course_run_3.course_run_state.name = CourseRunStateChoices.Draft
        self.course_run_3.course_run_state.save()
        response = self.assert_dashboard_response(
            studio_count=3, published_count=0, progress_count=3, preview_count=1, queries_executed=24
        )
        self.assertContains(response, 'No About pages have been published yet')
        self._assert_tabs_with_roles(response)

    def test_published_course_runs(self):
        """ Verify that published tab loads course runs list. """
        response = self.assert_dashboard_response(
            studio_count=2, published_count=1, progress_count=2, preview_count=1, queries_executed=23
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
            studio_count=0, published_count=0, progress_count=0, preview_count=0, queries_executed=15
        )

        # assign user course role
        factories.CourseUserRoleFactory(
            course=self.course_run_3.course, user=internal_user, role=PublisherUserRole.ProjectCoordinator
        )

        # Verify that user can see 1 published course run
        response = self.assert_dashboard_response(
            studio_count=0, published_count=1, progress_count=0, preview_count=0, queries_executed=16
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
            studio_count=4, published_count=1, progress_count=3, preview_count=1, queries_executed=20
        )
        self._assert_tabs_with_roles(response)

    def test_with_preview_ready_course_runs(self):
        """ Verify that preview ready tabs loads the course runs list. """
        response = self.assert_dashboard_response(
            studio_count=2, preview_count=1, progress_count=2, published_count=1, queries_executed=23
        )
        self.assertContains(response, self.table_class.format(id='preview'))
        self.assertContains(response, 'About page previews for the following course runs are available for course team')
        self._assert_tabs_with_roles(response)

    def test_without_preview_ready_course_runs(self):
        """ Verify preview ready tabs shows a message if no course run available. """
        self.course_run_2.preview_url = None
        self.course_run_2.course_run_state.name = CourseRunStateChoices.Draft
        self.course_run_2.course_run_state.save()
        response = self.assert_dashboard_response(
            studio_count=2, preview_count=0, progress_count=3, published_count=1, queries_executed=22
        )
        self._assert_tabs_with_roles(response)

    def test_without_preview_url(self):
        """ Verify in preview tab shows course in "in review" tab if course run is approve regardless of
        preview url is added or not.
        """
        response = self.assert_dashboard_response(
            studio_count=2, preview_count=1, progress_count=2, published_count=1, queries_executed=23
        )
        self._assert_tabs_with_roles(response)

        # without preview url
        self.course_run_2.preview_url = None
        self.course_run_2.save()
        response = self.assert_dashboard_response(
            studio_count=2, preview_count=1, progress_count=2, published_count=1, queries_executed=23
        )
        self._assert_tabs_with_roles(response)

    def test_with_in_progress_course_runs(self):
        """ Verify that in progress tabs loads the course runs list. """
        response = self.assert_dashboard_response(
            studio_count=2, preview_count=1, progress_count=2, published_count=1, queries_executed=23
        )
        self.assertContains(response, self.table_class.format(id='in-progress'))
        self._assert_tabs_with_roles(response)

    def assert_dashboard_response(
        self, studio_count=0, published_count=0, progress_count=0, preview_count=0, queries_executed=0
    ):
        """ Dry method to assert the response."""
        with self.assertNumQueries(queries_executed):
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

        with self.assertNumQueries(11):
            response = self.client.get(self.page_url)

        for tab in ['progress', 'preview', 'studio', 'published']:
            self.assertContains(response, '<li role="tab" id="tab-{tab}" class="tab"'.format(tab=tab))

    def test_site_name(self):
        """
        Verify that site_name is available in context.
        """
        with self.assertNumQueries(23):
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

        with self.assertNumQueries(25):
            response = self.client.get(self.page_url)

        site = Site.objects.first()
        self._assert_filter_counts(response, 'All', 3)
        self._assert_filter_counts(response, 'With Course Team', 2)
        self._assert_filter_counts(response, 'With {site_name}'.format(site_name=site.name), 1)

    def _assert_filter_counts(self, response, expected_label, count):
        """
        Assert label and course run count for filters.
        """
        self.assertContains(response, expected_label, count=1)
        expected_count = '<span class="filter-count">{count}</span>'.format(count=count)
        self.assertContains(response, expected_count, count=1)


class ToggleEmailNotificationTests(TestCase):
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


class CourseListViewTests(TestCase):
    """ Tests for `CourseListView` """

    def setUp(self):
        super(CourseListViewTests, self).setUp()
        self.courses = [factories.CourseFactory() for _ in range(10)]
        self.course = self.courses[0]
        self.user = UserFactory()

        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.courses_url = reverse('publisher:publisher_courses')

    def test_courses_with_no_courses(self):
        """ Verify that user cannot see any course on course list page. """
        self.assert_course_list_page(course_count=0, queries_executed=8)

    def test_courses_with_admin(self):
        """ Verify that admin user can see all courses on course list page. """
        self.user.groups.add(Group.objects.get(name=ADMIN_GROUP_NAME))
        self.assert_course_list_page(course_count=10, queries_executed=31)

    def test_courses_with_course_user_role(self):
        """ Verify that internal user can see course on course list page. """
        self.user.groups.add(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))
        for course in self.courses:
            factories.CourseUserRoleFactory(course=course, user=self.user, role=InternalUserRole.Publisher)

        self.assert_course_list_page(course_count=10, queries_executed=32)

    def test_courses_with_permission(self):
        """ Verify that user can see course with permission on course list page. """
        organization_extension = factories.OrganizationExtensionFactory()
        self.user.groups.add(organization_extension.group)

        for course in self.courses:
            course.organizations.add(organization_extension.organization)

        assign_perm(OrganizationExtension.VIEW_COURSE, organization_extension.group, organization_extension)
        self.assert_course_list_page(course_count=10, queries_executed=64)

    def assert_course_list_page(self, course_count, queries_executed):
        """ Dry method to assert course list page content. """
        with self.assertNumQueries(queries_executed):
            response = self.client.get(self.courses_url)

        self.assertContains(response, '{} Courses'.format(course_count))
        self.assertContains(response, 'Create New Course')
        if course_count > 0:
            self.assertContains(response, self.course.title)

    def test_page_with_enable_waffle_switch(self):
        """
        Verify that edit button will not be shown if 'publisher_hide_features_for_pilot' activated.
        """
        factories.CourseUserRoleFactory(course=self.course, user=self.user, role=PublisherUserRole.CourseTeam)
        organization_extension = factories.OrganizationExtensionFactory()
        self.course.organizations.add(organization_extension.organization)
        self.user.groups.add(organization_extension.group)
        assign_perm(OrganizationExtension.VIEW_COURSE, organization_extension.group, organization_extension)
        assign_perm(OrganizationExtension.EDIT_COURSE, organization_extension.group, organization_extension)
        response = self.client.get(self.courses_url)
        self.assertContains(response, 'Edit')

        toggle_switch('publisher_hide_features_for_pilot', True)

        with self.assertNumQueries(17):
            response = self.client.get(self.courses_url)

        self.assertNotContains(response, 'Edit')

    def test_page_with_disable_waffle_switch(self):
        """
        Verify that edit button will be shown if 'publisher_hide_features_for_pilot' deactivated.
        """
        organization_extension = factories.OrganizationExtensionFactory()
        self.course.organizations.add(organization_extension.organization)
        self.user.groups.add(organization_extension.group)
        factories.CourseUserRoleFactory(course=self.course, user=self.user, role=PublisherUserRole.CourseTeam)

        assign_perm(OrganizationExtension.VIEW_COURSE, organization_extension.group, organization_extension)
        assign_perm(OrganizationExtension.EDIT_COURSE, organization_extension.group, organization_extension)

        toggle_switch('publisher_hide_features_for_pilot', False)

        with self.assertNumQueries(21):
            response = self.client.get(self.courses_url)

        self.assertContains(response, 'Edit')


class CourseDetailViewTests(TestCase):
    """ Tests for the course detail view. """

    def setUp(self):
        super(CourseDetailViewTests, self).setUp()
        self.course = factories.CourseFactory()
        self.user = UserFactory()
        self.client.login(username=self.user.username, password=USER_PASSWORD)

        self.organization_extension = factories.OrganizationExtensionFactory()
        self.course.organizations.add(self.organization_extension.organization)

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
        self.assertEqual(response.context['breadcrumbs'][1]['slug'], self.course.title)

    def test_details_page_with_course_runs_lms_id(self):
        """ Test that user can see course runs with lms-id on course detail page. """
        self.user.groups.add(self.organization_extension.group)
        assign_perm(OrganizationExtension.VIEW_COURSE, self.organization_extension.group, self.organization_extension)

        lms_course_id = 'test/id'
        factories.CourseRunFactory(course=self.course, lms_course_id=lms_course_id)
        response = self.client.get(self.detail_page_url)
        self.assertContains(response, 'course/{}'.format(lms_course_id))

    def test_page_enable_waffle_switch_pilot(self):
        """ Verify that user will not see approval widget when 'publisher_hide_features_for_pilot' is activated. """
        self.user.groups.add(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))
        toggle_switch('publisher_hide_features_for_pilot', True)
        response = self.client.get(self.detail_page_url)

        self.assertContains(response, '<div id="approval-widget" class="hidden">')

    def test_page_disable_waffle_switch_pilot(self):
        """ Verify that user will see approval widget when 'publisher_hide_features_for_pilot' is deactivated. """
        self.user.groups.add(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))
        toggle_switch('publisher_hide_features_for_pilot', False)
        response = self.client.get(self.detail_page_url)

        self.assertContains(response, '<div id="approval-widget" class="">')

    def test_comments_with_enable_switch(self):
        """ Verify that user will see the comments widget when
        'publisher_comment_widget_feature' is enabled.
        """
        self.user.groups.add(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))
        toggle_switch('publisher_comment_widget_feature', True)
        response = self.client.get(self.detail_page_url)

        self.assertContains(response, '<div id="comments-widget" class="comment-container ">')

    def test_comments_with_disable_switch(self):
        """ Verify that user will not see the comments widget when
        'publisher_comment_widget_feature' is disabled.
        """
        self.user.groups.add(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))
        toggle_switch('publisher_comment_widget_feature', False)
        response = self.client.get(self.detail_page_url)
        self.assertContains(response, '<div id="comments-widget" class="comment-container hidden">')

    def test_history_with_enable_switch(self):
        """ Verify that user will see the history widget when
        'publisher_history_widget_feature' is enabled.
        """
        # Update course to create multiple history objects.
        self.course.title = 'Updated Test Title'
        self.course.save()
        self.user.groups.add(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))
        toggle_switch('publisher_history_widget_feature', True)
        response = self.client.get(self.detail_page_url)
        self.assertContains(response, '<div class="history-widget ">')

    def test_history_with_disable_switch(self):
        """ Verify that user will not see the history widget when
        'publisher_history_widget_feature' is disabled.
        """
        # Update course to create multiple history objects.
        self.course.title = 'Updated Test Title'
        self.course.save()
        self.user.groups.add(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))
        toggle_switch('publisher_history_widget_feature', False)
        response = self.client.get(self.detail_page_url)
        self.assertContains(response, '<div class="history-widget hidden">')

    def test_approval_widget_with_enable_switch(self):
        """ Verify that user will see the history widget when
        'publisher_approval_widget_feature' is enabled.
        """
        self.user.groups.add(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))
        toggle_switch('publisher_approval_widget_feature', True)
        response = self.client.get(self.detail_page_url)
        self.assertContains(response, '<div class="approval-widget ">')

    def test_approval_widget_with_disable_switch(self):
        """ Verify that user will not see the history widget when
        'publisher_approval_widget_feature' is disabled.
        """
        self.user.groups.add(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))
        toggle_switch('publisher_approval_widget_feature', False)
        response = self.client.get(self.detail_page_url)
        self.assertContains(response, '<div class="approval-widget hidden">')

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

        response = self.client.get(self.detail_page_url)

        # Verify that user cannot see history widget if there is only one history object.
        self.assertEqual(self.course.history.count(), 1)
        self.assertNotContains(response, 'REVISION HISTORY')

        # Update course to create multiple history objects.
        self.course.title = 'Updated Test Title'
        self.course.save()

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
        self.assertEqual(response.context['breadcrumbs'][1]['slug'], title)

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
class CourseEditViewTests(TestCase):
    """ Tests for the course edit view. """

    def setUp(self):
        super(CourseEditViewTests, self).setUp()
        self.course = factories.CourseFactory()
        self.user = UserFactory()
        self.course_team_user = UserFactory()
        self.client.login(username=self.user.username, password=USER_PASSWORD)

        self.organization_extension = factories.OrganizationExtensionFactory()
        self.course.organizations.add(self.organization_extension.organization)

        # Initialize workflow for Course.
        CourseState.objects.create(course=self.course, owner_role=PublisherUserRole.CourseTeam)

        self.course_team_role = factories.CourseUserRoleFactory(
            course=self.course, role=PublisherUserRole.CourseTeam, user=self.user
        )
        self.organization_extension.group.user_set.add(*(self.user, self.course_team_user))

        self.edit_page_url = reverse('publisher:publisher_courses_edit', args=[self.course.id])

    def test_edit_page_without_permission(self):
        """
        Verify that user cannot access course edit page without edit permission.
        """
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

    def test_update_course_with_admin(self):
        """
        Verify that publisher admin can update an existing course.
        """

        # only 1 history object exists for a course.
        self.assertEqual(self.course.history.all().count(), 1)

        self.user.groups.add(Group.objects.get(name=ADMIN_GROUP_NAME))
        post_data = self._post_data(self.organization_extension)

        updated_course_title = 'Updated {}'.format(self.course.title)
        post_data['title'] = updated_course_title
        post_data['short_description'] = 'Testing description'

        self.assertNotEqual(self.course.title, updated_course_title)
        self.assertNotEqual(self.course.changed_by, self.user)

        response = self.client.post(self.edit_page_url, data=post_data)

        self.assertRedirects(
            response,
            expected_url=reverse('publisher:publisher_course_detail', kwargs={'pk': self.course.id}),
            status_code=302,
            target_status_code=200
        )

        course = Course.objects.get(id=self.course.id)
        # Assert that course is updated.
        self.assertEqual(course.title, updated_course_title)
        self.assertEqual(course.changed_by, self.user)
        self.assertEqual(course.short_description, 'Testing description')

        # After updating 2 history object exists for a course.
        self.assertEqual(self.course.history.all().count(), 2)

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

        response = self.client.post(self.edit_page_url, data=self._post_data(self.organization_extension))

        self.assertRedirects(
            response,
            expected_url=reverse('publisher:publisher_course_detail', kwargs={'pk': self.course.id}),
            status_code=302,
            target_status_code=200
        )

        self.assertEqual(self.course.course_team_admin, self.course_team_user)
        self.assertEqual(self.course.history.all().count(), 2)

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

        response = self.client.post(self.edit_page_url, data=self._post_data(organization_extension))

        self.assertRedirects(
            response,
            expected_url=reverse('publisher:publisher_course_detail', kwargs={'pk': self.course.id}),
            status_code=302,
            target_status_code=200
        )

        self.assertEqual(self.course.organizations.first(), organization_extension.organization)
        self.assertEqual(self.course.history.all().count(), 2)

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

        response = self.client.post(self.edit_page_url, data=post_data)

        self.assertRedirects(
            response,
            expected_url=reverse('publisher:publisher_course_detail', kwargs={'pk': self.course.id}),
            status_code=302,
            target_status_code=200
        )

        course_state = CourseState.objects.get(id=self.course.course_state.id)
        self.assertEqual(course_state.name, CourseStateChoices.Draft)

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

        response = self.client.post(self.edit_page_url, data=post_data)

        self.assertRedirects(
            response,
            expected_url=reverse('publisher:publisher_course_detail', kwargs={'pk': self.course.id}),
            status_code=302,
            target_status_code=200
        )

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

    def test_update_with_errors(self):
        """
        Verify that page shows error if any required field data is missing.
        """
        self.user.groups.add(Group.objects.get(name=ADMIN_GROUP_NAME))
        post_data = self._post_data(self.organization_extension)

        post_data['title'] = ''
        response = self.client.post(self.edit_page_url, data=post_data)
        self.assertContains(response, 'The page could not be updated. Make sure that')

    def test_text_area_max_length_error(self):
        """
        Verify that page shows error if any text area exceeds the max length.
        """
        self.user.groups.add(Group.objects.get(name=ADMIN_GROUP_NAME))
        post_data = self._post_data(self.organization_extension)
        post_data['title'] = 'test'
        post_data['short_description'] = '''
            <html>
                <body>
                <h2>An Unordered HTML List</h2>
                <ul>
                  <li>An Unordered HTML List. An Unordered HTML List</li>
                  <li>An Unordered HTML List. An Unordered HTML List</li>
                  <li>An Unordered HTML List</li>
                </ul>
                <ul>
                  <li>An Unordered HTML List</li>
                  <li>An Unordered HTML List</li>
                  <li>An Unordered HTML List</li>
                </ul>
                <ul>
                  <li>An Unordered HTML List</li>
                  <li>An Unordered HTML List</li>
                  <li>An Unordered HTML List</li>
                </ul>
                </body>
            </html>
        '''
        response = self.client.post(self.edit_page_url, data=post_data)

        self.assertContains(response, 'Ensure this value has at most 255 characters')

    @ddt.data(
        'short_description', 'full_description', 'prerequisites', 'expected_learnings',
        'learner_testimonial', 'faq', 'syllabus'
    )
    def test_text_area_post_with_html(self, field):
        """
        Verify that page saves the text area html in db.
        """
        self.user.groups.add(Group.objects.get(name=ADMIN_GROUP_NAME))
        post_data = self._post_data(self.organization_extension)
        post_data['title'] = 'test'
        post_data[field] = '''
            <html>
                <body>
                <h2>An Unordered HTML List</h2>
                <ul>
                  <li>Coffee</li>
                  <li>Tea</li>
                </ul>
                </body>
            </html>
        '''

        response = self.client.post(self.edit_page_url, data=post_data)
        self.assertRedirects(
            response,
            expected_url=reverse('publisher:publisher_course_detail', kwargs={'pk': self.course.id}),
            status_code=302,
            target_status_code=200
        )
        course = Course.objects.get(id=self.course.id)
        self.assertEqual(post_data[field].strip(), getattr(course, field).strip())

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

    def test_course_with_published_course_run(self):
        """
        Verify that editing course with published course run does not changed state
        and an email is sent to Publisher.
        """
        toggle_switch('enable_publisher_email_notifications', True)
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

        response = self.client.post(self.edit_page_url, data=post_data)

        self.assertRedirects(
            response,
            expected_url=reverse('publisher:publisher_course_detail', kwargs={'pk': self.course.id}),
            status_code=302,
            target_status_code=200
        )

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


@ddt.ddt
class CourseRunEditViewTests(TestCase):
    """ Tests for the course run edit view. """

    def setUp(self):
        super(CourseRunEditViewTests, self).setUp()

        self.user = UserFactory()
        self.organization_extension = factories.OrganizationExtensionFactory()
        self.group = self.organization_extension.group
        self.user.groups.add(self.group)

        self.group_project_coordinator = Group.objects.get(name=PROJECT_COORDINATOR_GROUP_NAME)

        self.course = factories.CourseFactory()
        self.course_run = factories.CourseRunFactory(course=self.course)
        self.seat = factories.SeatFactory(course_run=self.course_run, type=Seat.VERIFIED, price=2)

        self.course.organizations.add(self.organization_extension.organization)
        self.site = Site.objects.get(pk=settings.SITE_ID)
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
        data = {'number': 'course_update_1', 'image': '', 'title': 'test course'}
        self.user.groups.add(Group.objects.get(name=ADMIN_GROUP_NAME))
        course_dict = self._post_data(data, self.course, self.course_run)
        self.client.post(reverse('publisher:publisher_courses_new'), course_dict, files=data['image'])

        # newly created course from the page.
        self.new_course = Course.objects.get(number=data['number'])
        self.new_course_run = factories.CourseRunFactory(course=self.new_course)
        factories.CourseRunStateFactory(course_run=self.new_course_run, owner_role=PublisherUserRole.CourseTeam)

        assign_perm(OrganizationExtension.EDIT_COURSE_RUN, self.group, self.organization_extension)
        assign_perm(OrganizationExtension.VIEW_COURSE_RUN, self.group, self.organization_extension)

        # assert edit page is loading sucesfully.
        self.edit_page_url = reverse('publisher:publisher_course_runs_edit', kwargs={'pk': self.new_course_run.id})
        response = self.client.get(self.edit_page_url)
        self.assertEqual(response.status_code, 200)

        # Update the data for course
        data = {'full_description': 'This is testing description.', 'image': ''}
        self.updated_dict = self._post_data(data, self.new_course, self.new_course_run)

        # Update the data for course-run
        self.updated_dict['is_xseries'] = True
        self.updated_dict['xseries_name'] = 'Test XSeries'

        toggle_switch('enable_publisher_email_notifications', True)

    def _post_data(self, data, course, course_run):
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
        with patch.object(CourseRun, "save") as mock_method:
            mock_method.side_effect = IntegrityError
            response = self.client.post(self.edit_page_url, self.updated_dict)

            self.assertEqual(response.status_code, 400)
            updated_course = Course.objects.get(id=self.new_course.id)
            self.assertNotEqual(updated_course.full_description, 'This is testing description.')

            course_run = CourseRun.objects.get(id=self.new_course_run.id)
            self.assertNotEqual(course_run.xseries_name, 'Test XSeries')

    def test_update_course_run_with_seat(self):
        """ Verify that course run edit page create seat object also if not exists previously."""

        self.client.logout()
        user = self.new_course_run.course.course_user_roles.get(role=PublisherUserRole.CourseTeam).user
        self.client.login(username=user.username, password=USER_PASSWORD)
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

        course_run = CourseRun.objects.get(id=self.new_course_run.id)

        self.assertEqual(course_run.seats.first().type, Seat.PROFESSIONAL)
        self.assertEqual(course_run.seats.first().price, 10)

        self.assertEqual(course_run.seats.first().history.all().count(), 1)

    def test_logging(self):
        """ Verify view logs the errors in case of errors. """
        with patch('django.forms.models.BaseModelForm.is_valid') as mocked_is_valid:
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
        self.assertEqual(self.new_course_run.course_run_state.name, CourseRunStateChoices.Review)
        response = self.client.post(self.edit_page_url, self.updated_dict)

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
        page_url = 'https://{host}{path}'.format(host=Site.objects.get_current().domain.strip('/'), path=object_path)
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
        self.assertNotContains(response, '<div id="SeatPriceBlock" class="col col-6 hidden" style="display: block;">')

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
        self.assertContains(response, '<div id="SeatPriceBlock" class="col col-6')

    def test_page_with_enable_waffle_switch(self):
        """
        Verify that edit pages shows the about page information block but only visible
        if the switch `publisher_hide_features_for_pilot` is enable.
        """
        toggle_switch('publisher_hide_features_for_pilot', True)
        response = self.client.get(self.edit_page_url)
        self.assertContains(response, '<div id="about-page" class="course-information hidden">')

    def test_page_with_disable_waffle_switch(self):
        """
        Verify that edit pages shows the about page information block but hidden
        if the switch `publisher_hide_features_for_pilot` is disable
        """
        toggle_switch('publisher_hide_features_for_pilot', False)
        response = self.client.get(self.edit_page_url)
        self.assertContains(response, '<div id="about-page" class="course-information ">')

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
        Verify that `lms_course_id` not getting blanked if course team updates with empty value.
        """
        self.client.logout()
        user = self.new_course.course_team_admin
        self.client.login(username=user.username, password=USER_PASSWORD)

        post_data = self._post_data({'image': ''}, self.new_course, self.new_course_run)
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


class CourseRevisionViewTests(TestCase):
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


class CreateRunFromDashboardViewTests(TestCase):
    """ Tests for the publisher `CreateRunFromDashboardView`. """

    def setUp(self):
        super(CreateRunFromDashboardViewTests, self).setUp()
        self.user = UserFactory()
        self.course = factories.CourseFactory()
        factories.CourseStateFactory(course=self.course)
        factories.CourseUserRoleFactory.create(course=self.course, role=PublisherUserRole.CourseTeam, user=self.user)
        factories.CourseUserRoleFactory.create(course=self.course, role=PublisherUserRole.Publisher, user=UserFactory())
        factories.CourseUserRoleFactory.create(
            course=self.course, role=PublisherUserRole.ProjectCoordinator, user=UserFactory()
        )
        factories.CourseUserRoleFactory.create(
            course=self.course, role=PublisherUserRole.MarketingReviewer, user=UserFactory()
        )

        self.organization_extension = factories.OrganizationExtensionFactory()
        self.course.organizations.add(self.organization_extension.organization)
        self.user.groups.add(self.organization_extension.group)

        assign_perm(
            OrganizationExtension.VIEW_COURSE_RUN, self.organization_extension.group, self.organization_extension
        )

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

    def test_create_course_run_and_seat(self):
        """ Verify that we can create a new course run with seat. """
        self.assertEqual(self.course.course_runs.count(), 0)
        new_user = factories.UserFactory()
        new_user.groups.add(self.organization_extension.group)

        self.assertEqual(self.course.course_team_admin, self.user)

        post_data = self._post_data()
        response = self.client.post(self.create_course_run_url, self._post_data())

        self.assertEqual(self.course.course_runs.count(), 1)

        new_seat = Seat.objects.get(type=post_data['type'], price=post_data['price'])
        self.assertRedirects(
            response,
            expected_url=reverse('publisher:publisher_course_run_detail', kwargs={'pk': new_seat.course_run.id}),
            status_code=302,
            target_status_code=200
        )

        self.assertEqual(new_seat.type, Seat.VERIFIED)
        self.assertEqual(new_seat.price, post_data['price'])

        # Verify that and email is sent for studio instance request to project coordinator.
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual([self.course.project_coordinator.email], mail.outbox[0].to)
        expected_subject = 'Studio URL requested: {title}'.format(title=self.course.title)
        self.assertEqual(str(mail.outbox[0].subject), expected_subject)


class CreateAdminImportCourseTest(TestCase):
    """ Tests for the publisher `CreateAdminImportCourse`. """

    def setUp(self):
        super(CreateAdminImportCourseTest, self).setUp()
        self.user = UserFactory()

        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.page_url = reverse('publisher:publisher_admin_import_course')

        self.course = CourseFactory()

    def test_page_without_login(self):
        """ Verify that user can't access page when not logged in. """
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

    def test_page_with_superuser_and_waffle(self):
        """ Verify that user can't access page when not logged in. """
        response = self._make_users_valid(True)
        self.assertEqual(response.status_code, 200)

    def test_page_with_superuser_without_waffle(self):
        """ Verify that user can't access page when not logged in. """
        response = self._make_users_valid(False)
        self.assertEqual(response.status_code, 404)

    def test_page_with_post(self):
        """ Verify page shows message with successful import. """

        # organization should be available for import
        self.course.authoring_organizations.add(OrganizationFactory())

        self._make_users_valid(True)
        post_data = {'start_id': self.course.pk}
        response = self.client.post(self.page_url, post_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Course Imported')

    def test_page_with_invalid_course_id(self):
        """ Verify page shows error message if import fails. """
        self._make_users_valid(True)
        post_data = {'start_id': 100}
        response = self.client.post(self.page_url, post_data)
        self.assertContains(response, 'Course matching query does not exist.')

    def test_import_with_failure(self):
        """ Verify page shows error in case of any error. """
        self._make_users_valid(True)
        post_data = {'start_id': self.course.pk}
        response = self.client.post(self.page_url, post_data)
        self.assertContains(response, 'Some error occurred')

    def test_course_user_roles_creation(self):
        """ Verify course add the course-users roles after importing the course. """
        # organization should be available for import
        organization = OrganizationFactory()
        self.course.authoring_organizations.add(organization)
        self._add_org_roles(organization)
        self._make_users_valid(True)

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
        self._make_users_valid(True)

        post_data = {'start_id': self.course.pk}
        response = self.client.post(self.page_url, post_data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Course Imported')

    def _make_users_valid(self, switch):
        """ make user eligible for the page."""
        self.client.logout()
        self.user.is_superuser = True
        self.user.save()

        toggle_switch('publisher_enable_course_import', switch)

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
