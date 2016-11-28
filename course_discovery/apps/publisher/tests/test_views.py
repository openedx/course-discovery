# pylint: disable=no-member
import json
from datetime import datetime

import ddt
import factory
from django.http import Http404
from mock import patch

from django.db import IntegrityError
from django.conf import settings
from django.contrib.sites.models import Site
from django.core import mail
from django.core.urlresolvers import reverse
from django.forms import model_to_dict
from django.test import TestCase
from testfixtures import LogCapture

from course_discovery.apps.core.models import User
from course_discovery.apps.core.tests.factories import UserFactory, USER_PASSWORD
from course_discovery.apps.core.tests.helpers import make_image_file
from course_discovery.apps.course_metadata.tests import toggle_switch
from course_discovery.apps.publisher.models import Course, CourseRun, Seat, State
from course_discovery.apps.publisher.tests import factories, JSON_CONTENT_TYPE
from course_discovery.apps.publisher.tests.utils import create_non_staff_user_and_login
from course_discovery.apps.publisher.utils import is_email_notification_enabled
from course_discovery.apps.publisher.views import CourseRunDetailView, logger as publisher_views_logger
from course_discovery.apps.publisher.wrappers import CourseRunWrapper
from course_discovery.apps.publisher_comments.tests.factories import CommentFactory


@ddt.ddt
class CreateUpdateCourseViewTests(TestCase):
    """ Tests for the publisher `CreateCourseView` and `UpdateCourseView`. """

    def setUp(self):
        super(CreateUpdateCourseViewTests, self).setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.group_organization_1 = factories.GroupOrganizationFactory()

        self.course = factories.CourseFactory(team_admin=self.user)
        self.course_run = factories.CourseRunFactory(course=self.course)
        self.seat = factories.SeatFactory(course_run=self.course_run, type=Seat.VERIFIED, price=2)

        self.user.groups.add(self.group_organization_1.group)
        self.site = Site.objects.get(pk=settings.SITE_ID)
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.start_date_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

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

    def test_create_course_and_course_run_and_seat_with_errors(self):
        """ Verify that without providing required data course and other
        objects cannot be created.
        """
        course_dict = model_to_dict(self.course)
        course_dict['number'] = 'test course'
        course_dict['image'] = ''
        response = self.client.post(reverse('publisher:publisher_courses_new'), course_dict)
        self.assertEqual(response.status_code, 400)

    @ddt.data(
        {'number': 'course_1', 'image': ''},
        {'number': 'course_2', 'image': make_image_file('test_banner.jpg')},
        {'number': 'course_3', 'image': make_image_file('test_banner1.jpg')}
    )
    def test_create_course_and_course_run_and_seat(self, data):
        """ Verify that new course, course run and seat can be created
        with different data sets.
        """
        self._assert_records(1)
        course_dict = self._post_data(data, self.course, self.course_run, self.seat)
        response = self.client.post(reverse('publisher:publisher_courses_new'), course_dict, files=data['image'])
        course = Course.objects.get(number=data['number'])

        if data['image']:
            self._assert_image(course)

        self._assert_test_data(response, course, self.seat.type, self.seat.price)

    def test_create_with_fail_transaction(self):
        """ Verify that in case of any error transactions roll back and no object
        created in db.
        """
        self._assert_records(1)
        data = {'number': 'course_2', 'image': make_image_file('test_banner.jpg')}
        course_dict = self._post_data(data, self.course, self.course_run, self.seat)
        with patch('course_discovery.apps.publisher.views.GroupOrganization') as mock_method:
            mock_method.side_effect = Http404
            response = self.client.post(reverse('publisher:publisher_courses_new'), course_dict, files=data['image'])

        self.assertEqual(response.status_code, 400)
        self._assert_records(1)

    def test_update_course_with_staff(self):
        """ Verify that staff user can update an existing course. """
        course_dict = model_to_dict(self.course)
        course_dict.pop('verification_deadline')
        course_dict.pop('image')
        course_dict.pop('team_admin')

        updated_course_title = 'Updated {}'.format(self.course.title)
        course_dict['title'] = updated_course_title
        self.assertNotEqual(self.course.title, updated_course_title)
        self.assertNotEqual(self.course.changed_by, self.user)
        response = self.client.post(
            reverse('publisher:publisher_courses_edit', kwargs={'pk': self.course.id}),
            course_dict
        )

        self.assertRedirects(
            response,
            expected_url=reverse('publisher:publisher_courses_edit', kwargs={'pk': self.course.id}),
            status_code=302,
            target_status_code=200
        )

        course = Course.objects.get(id=self.course.id)
        # Assert that course is updated.
        self.assertEqual(course.title, updated_course_title)
        self.assertEqual(course.changed_by, self.user)

        # add new and check the comment on edit page.
        comment = CommentFactory(content_object=self.course, user=self.user, site=self.site)
        response = self.client.get(reverse('publisher:publisher_courses_edit', kwargs={'pk': self.course.id}))
        self.assertContains(response, 'Total Comments 1')
        self.assertContains(response, 'Add new comment')
        self.assertContains(response, comment.comment)

    def test_course_edit_page_with_non_staff(self):
        """ Verify that non staff user can't access course edit page without permission. """
        non_staff_user, group = create_non_staff_user_and_login(self)

        course_dict = model_to_dict(self.course)
        updated_course_title = 'Updated {}'.format(self.course.title)
        course_dict['title'] = updated_course_title
        self.assertNotEqual(self.course.title, updated_course_title)
        response = self.client.get(
            reverse('publisher:publisher_courses_edit', kwargs={'pk': self.course.id})
        )

        self.assertEqual(response.status_code, 403)

        group_organization = factories.GroupOrganizationFactory(group=group)
        # assign user a group and assign view permission on that group
        non_staff_user.groups.add(group)

        self.course.organizations.add(group_organization.organization)

        response = self.client.get(
            reverse('publisher:publisher_courses_edit', kwargs={'pk': self.course.id})
        )

        self.assertEqual(response.status_code, 200)

    def test_update_course_with_non_staff(self):
        """ Tests for update course with non staff user. """
        non_staff_user, group = create_non_staff_user_and_login(self)
        course_dict = model_to_dict(self.course)
        course_dict.pop('verification_deadline')
        course_dict.pop('image')
        course_dict.pop('team_admin')

        updated_course_title = 'Updated {}'.format(self.course.title)
        course_dict['title'] = updated_course_title
        self.assertNotEqual(self.course.title, updated_course_title)
        response = self.client.post(
            reverse('publisher:publisher_courses_edit', kwargs={'pk': self.course.id}),
            course_dict
        )

        # verify that non staff user can't update course without permission
        self.assertEqual(response.status_code, 403)

        group_organization = factories.GroupOrganizationFactory(group=group)
        # assign user a group and assign view permission on that group
        non_staff_user.groups.add(group)

        self.course.organizations.add(group_organization.organization)

        response = self.client.post(
            reverse('publisher:publisher_courses_edit', kwargs={'pk': self.course.id}),
            course_dict
        )
        self.assertRedirects(
            response,
            expected_url=reverse('publisher:publisher_courses_edit', kwargs={'pk': self.course.id}),
            status_code=302,
            target_status_code=200
        )

        course = Course.objects.get(id=self.course.id)
        # Assert that course is updated.
        self.assertEqual(course.title, updated_course_title)

        # add new and check the comment on edit page.
        comment = CommentFactory(content_object=self.course, user=self.user, site=self.site)
        response = self.client.get(reverse('publisher:publisher_courses_edit', kwargs={'pk': self.course.id}))
        self.assertContains(response, 'Total Comments 1')
        self.assertContains(response, 'Add new comment')
        self.assertContains(response, comment.comment)

    @ddt.data(Seat.VERIFIED, Seat.PROFESSIONAL, Seat.NO_ID_PROFESSIONAL, Seat.CREDIT)
    def test_create_course_without_price_with_error(self, seat_type):
        """ Verify that if seat type is not honor/audit then price should be given.
        Otherwise it will throw error.
        """
        self._assert_records(1)
        data = {'number': 'course_1', 'image': ''}
        course_dict = self._post_data(data, self.course, self.course_run, self.seat)
        course_dict['price'] = 0
        course_dict['type'] = seat_type
        response = self.client.post(reverse('publisher:publisher_courses_new'), course_dict, files=data['image'])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.context['seat_form'].errors['price'][0], 'Only honor/audit seats can be without price.'
        )
        self._assert_records(1)

    @ddt.data(Seat.AUDIT, Seat.HONOR)
    def test_create_course_without_price_with_success(self, seat_type):
        """ Verify that if seat type is honor/audit then price is not required. """
        self._assert_records(1)
        data = {'number': 'course_1', 'image': ''}
        course_dict = self._post_data(data, self.course, self.course_run, self.seat)
        course_dict['price'] = 0
        course_dict['type'] = seat_type
        response = self.client.post(reverse('publisher:publisher_courses_new'), course_dict, files=data['image'])
        course = Course.objects.get(number=data['number'])
        self._assert_test_data(response, course, seat_type, 0)

    def _post_data(self, data, course, course_run, seat):
        course_dict = model_to_dict(course)
        course_dict.update(**data)
        course_dict['keywords'] = 'abc def xyz'
        if course_run:
            course_dict.update(**model_to_dict(course_run))
            course_dict.pop('video_language')
            course_dict.pop('end')
            course_dict.pop('priority')
            course_dict['start'] = self.start_date_time
            course_dict['organization'] = self.group_organization_1.organization.id
        if seat:
            course_dict.update(**model_to_dict(seat))
            course_dict.pop('verification_deadline')

        return course_dict

    def _assert_image(self, course):
        image_url_prefix = '{}media/publisher/courses/images'.format(settings.MEDIA_URL)
        self.assertIn(image_url_prefix, course.image.url)
        for size_key in course.image.field.variations:
            # Get different sizes specs from the model field
            # Then get the file path from the available files
            sized_file = getattr(course.image, size_key, None)
            self.assertIsNotNone(sized_file)
            self.assertIn(image_url_prefix, sized_file.url)

    def _assert_records(self, count):
        # DRY method to count records in db.
        self.assertEqual(Course.objects.all().count(), count)
        self.assertEqual(CourseRun.objects.all().count(), count)
        self.assertEqual(Seat.objects.all().count(), count)

    def _assert_test_data(self, response, course, expected_type, expected_price):
        # DRY method to assert response and data.
        self.assertRedirects(
            response,
            expected_url=reverse('publisher:publisher_courses_readonly', kwargs={'pk': course.id}),
            status_code=302,
            target_status_code=200
        )
        # self.assertEqual(course.group_institution, self.group_organization_1)
        self.assertEqual(course.team_admin, self.user)
        self.assertTrue(self.user.has_perm(Course.VIEW_PERMISSION, course))
        course_run = course.publisher_course_runs.all()[0]
        self.assertEqual(self.course_run.language, course_run.language)
        self.assertEqual(course_run.start.strftime("%Y-%m-%d %H:%M:%S"), self.start_date_time)
        seat = course_run.seats.all()[0]
        self.assertEqual(seat.type, expected_type)
        self.assertEqual(seat.price, expected_price)
        self._assert_records(2)
        response = self.client.get(reverse('publisher:publisher_courses_readonly', kwargs={'pk': course.id}))
        self.assertEqual(response.status_code, 200)

        # django-taggit stores data without any order. For test .
        self.assertEqual(sorted([c.name for c in course.keywords.all()]), ['abc', 'def', 'xyz'])


class CreateUpdateCourseRunViewTests(TestCase):
    """ Tests for the publisher `CreateCourseRunView` and `UpdateCourseRunView`. """

    def setUp(self):
        super(CreateUpdateCourseRunViewTests, self).setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.course = factories.CourseFactory(team_admin=self.user)
        self.course_run = factories.CourseRunFactory()
        self.course_run_dict = model_to_dict(self.course_run)
        self.course_run_dict.update(
            {'number': self.course.number, 'team_admin': self.course.team_admin.id, 'is_self_paced': True}
        )
        self._pop_valuse_from_dict(
            self.course_run_dict,
            [
                'end', 'enrollment_start', 'enrollment_end',
                'priority', 'certificate_generation', 'video_language'
            ]
        )
        self.course_run_dict['start'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
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

    def test_create_course_run_and_seat_with_errors(self):
        """ Verify that without providing required data course run and seat
        cannot be created.
        """
        response = self.client.post(
            reverse('publisher:publisher_course_runs_new', kwargs={'parent_course_id': self.course.id}),
            self.course_run_dict
        )
        self.assertEqual(response.status_code, 400)

        post_data = model_to_dict(self.course)
        post_data.update(self.course_run_dict)
        post_data.update(factory.build(dict, FACTORY_CLASS=factories.SeatFactory))
        self._pop_valuse_from_dict(post_data, ['id', 'upgrade_deadline', 'image', 'team_admin'])

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
        updated_course_number = '{number}.2'.format(number=self.course.number)
        new_price = 450
        post_data = self.course_run_dict
        seat = factories.SeatFactory(course_run=self.course_run, type=Seat.HONOR, price=0)
        post_data.update(**model_to_dict(seat))
        post_data.update(
            {
                'number': updated_course_number,
                'type': Seat.VERIFIED,
                'price': new_price
            }
        )
        self._pop_valuse_from_dict(post_data, ['id', 'course', 'course_run'])

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

        self.course = new_seat.course_run.course
        # Verify that number is updated for parent course
        self.assertEqual(self.course.number, updated_course_number)

    def test_update_course_run_with_staff(self):
        """ Verify that staff user can update an existing course run. """
        updated_lms_course_id = 'course-v1:testX+AS121+2018_q1'
        self.course_run_dict['lms_course_id'] = updated_lms_course_id

        self.assertNotEqual(self.course_run.lms_course_id, updated_lms_course_id)
        self.assertNotEqual(self.course_run.changed_by, self.user)
        response = self.client.post(
            reverse('publisher:publisher_course_runs_edit', kwargs={'pk': self.course_run.id}),
            self.course_run_dict
        )

        self.assertRedirects(
            response,
            expected_url=reverse('publisher:publisher_course_runs_edit', kwargs={'pk': self.course_run.id}),
            status_code=302,
            target_status_code=200
        )

        course_run = CourseRun.objects.get(id=self.course_run.id)
        # Assert that course run is updated.
        self.assertEqual(course_run.lms_course_id, updated_lms_course_id)
        self.assertEqual(course_run.changed_by, self.user)

        # add new and check the comment on edit page.
        comment = CommentFactory(content_object=self.course_run, user=self.user, site=self.site)
        response = self.client.get(reverse('publisher:publisher_course_runs_edit', kwargs={'pk': self.course_run.id}))
        self.assertContains(response, 'Total Comments 1')
        self.assertContains(response, 'Add new comment')
        self.assertContains(response, comment.comment)

    def test_edit_course_run_page_with_non_staff(self):
        """ Verify that non staff user can't access course run edit page without permission. """
        non_staff_user, group = create_non_staff_user_and_login(self)

        updated_lms_course_id = 'course-v1:testX+AS121+2018_q1'
        self.course_run_dict['lms_course_id'] = updated_lms_course_id
        self.assertNotEqual(self.course_run.lms_course_id, updated_lms_course_id)

        response = self.client.get(
            reverse('publisher:publisher_course_runs_edit', kwargs={'pk': self.course_run.id})
        )

        self.assertEqual(response.status_code, 403)

        group_organization = factories.GroupOrganizationFactory(group=group)
        # assign user a group and assign view permission on that group
        non_staff_user.groups.add(group)

        self.course_run.course.organizations.add(group_organization.organization)

        response = self.client.get(
            reverse('publisher:publisher_course_runs_edit', kwargs={'pk': self.course_run.id})
        )

        self.assertEqual(response.status_code, 200)

    def test_update_course_run_with_non_staff(self):
        """ Test for course run with non staff user. """
        non_staff_user, group = create_non_staff_user_and_login(self)

        updated_lms_course_id = 'course-v1:testX+AS121+2018_q1'
        self.course_run_dict['lms_course_id'] = updated_lms_course_id
        self.assertNotEqual(self.course_run.lms_course_id, updated_lms_course_id)

        response = self.client.post(
            reverse('publisher:publisher_course_runs_edit', kwargs={'pk': self.course_run.id}),
            self.course_run_dict
        )

        # verify that non staff user can't update course run without permission
        self.assertEqual(response.status_code, 403)

        # assign user a group and assign view permission on that group
        group_organization = factories.GroupOrganizationFactory(group=group)
        # assign user a group and assign view permission on that group
        non_staff_user.groups.add(group)

        self.course_run.course.organizations.add(group_organization.organization)

        response = self.client.post(
            reverse('publisher:publisher_course_runs_edit', kwargs={'pk': self.course_run.id}),
            self.course_run_dict
        )

        self.assertRedirects(
            response,
            expected_url=reverse('publisher:publisher_course_runs_edit', kwargs={'pk': self.course_run.id}),
            status_code=302,
            target_status_code=200
        )

        course_run = CourseRun.objects.get(id=self.course_run.id)
        # Assert that course run is updated.
        self.assertEqual(course_run.lms_course_id, updated_lms_course_id)

        # add new and check the comment on edit page.
        comment = CommentFactory(content_object=self.course_run, user=self.user, site=self.site)
        response = self.client.get(reverse('publisher:publisher_course_runs_edit', kwargs={'pk': self.course_run.id}))
        self.assertContains(response, 'Total Comments 1')
        self.assertContains(response, 'Add new comment')
        self.assertContains(response, comment.comment)


class SeatsCreateUpdateViewTests(TestCase):
    """ Tests for the publisher `CreateSeatView` and `UpdateSeatView`. """

    def setUp(self):
        super(SeatsCreateUpdateViewTests, self).setUp()
        self.seat = factories.SeatFactory(type=Seat.PROFESSIONAL, credit_hours=0)
        self.seat_dict = model_to_dict(self.seat)
        self.seat_dict.pop('upgrade_deadline')
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.site = Site.objects.get(pk=settings.SITE_ID)
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.seat_edit_url = reverse('publisher:publisher_seats_edit', kwargs={'pk': self.seat.id})
        self.group_organization_1 = factories.GroupOrganizationFactory()

    def test_seat_form_without_login(self):
        """ Verify that user can't access new seat form page when not logged in. """
        self.client.logout()
        response = self.client.get(reverse('publisher:publisher_seats_new'))

        self.assertRedirects(
            response,
            expected_url='{url}?next={next}'.format(
                url=reverse('login'),
                next=reverse('publisher:publisher_seats_new')
            ),
            status_code=302,
            target_status_code=302
        )

    def test_seat_view_page(self):
        """ Verify that we can open new seat page. """
        response = self.client.get(reverse('publisher:publisher_seats_new'))
        # Assert that we can load seat page.
        self.assertEqual(response.status_code, 200)

    def test_create_seat(self):
        """ Verify that we can create a new seat. """
        seat_price = 670.00
        self.seat_dict['price'] = seat_price
        response = self.client.post(reverse('publisher:publisher_seats_new'), self.seat_dict)
        seat = Seat.objects.get(course_run=self.seat.course_run, price=seat_price)
        self.assertRedirects(
            response,
            expected_url=reverse('publisher:publisher_seats_edit', kwargs={'pk': seat.id}),
            status_code=302,
            target_status_code=200
        )

        self.assertEqual(seat.price, seat_price)

    def test_update_seat_with_staff(self):
        """ Verify that staff user can update an existing seat. """
        self.assertEqual(self.seat.type, Seat.PROFESSIONAL)
        updated_seat_price = 470.00
        self.seat_dict['price'] = updated_seat_price
        self.seat_dict['type'] = Seat.VERIFIED
        self.assertNotEqual(self.seat.price, updated_seat_price)
        self.assertNotEqual(self.seat.changed_by, self.user)
        response = self.client.post(
            reverse('publisher:publisher_seats_edit', kwargs={'pk': self.seat.id}),
            self.seat_dict
        )

        self.assertRedirects(
            response,
            expected_url=self.seat_edit_url,
            status_code=302,
            target_status_code=200
        )

        seat = Seat.objects.get(id=self.seat.id)
        # Assert that seat is updated.
        self.assertEqual(seat.price, updated_seat_price)
        self.assertEqual(seat.changed_by, self.user)
        self.assertEqual(seat.type, Seat.VERIFIED)

        self.seat_dict['type'] = Seat.HONOR
        response = self.client.post(self.seat_edit_url, self.seat_dict)
        seat = Seat.objects.get(id=self.seat.id)
        # Assert that we can change seat type.
        self.assertEqual(seat.type, Seat.HONOR)

        self.assertRedirects(
            response,
            expected_url=self.seat_edit_url,
            status_code=302,
            target_status_code=200
        )

        # add new and check the comment on edit page.
        comment = CommentFactory(content_object=self.seat, user=self.user, site=self.site)
        response = self.client.get(self.seat_edit_url)
        self.assertContains(response, 'Total Comments 1')
        self.assertContains(response, 'Add new comment')
        self.assertContains(response, comment.comment)

    def test_edit_seat_page_with_non_staff(self):
        """ Verify that non staff user can't access seat edit page without permission. """
        non_staff_user, group = create_non_staff_user_and_login(self)
        response = self.client.get(reverse('publisher:publisher_seats_edit', kwargs={'pk': self.seat.id}))

        self.assertEqual(response.status_code, 403)

        # assign user a group and assign organization to the course
        group_organization_1 = factories.GroupOrganizationFactory(group=group)
        non_staff_user.groups.add(group_organization_1.group)
        self.seat.course_run.course.organizations.add(group_organization_1.organization)

        response = self.client.get(reverse('publisher:publisher_seats_edit', kwargs={'pk': self.seat.id}))

        self.assertEqual(response.status_code, 200)

    def test_update_seat_with_non_staff(self):
        """ Tests update seat for non staff user. """
        non_staff_user, group = create_non_staff_user_and_login(self)

        self.assertEqual(self.seat.type, Seat.PROFESSIONAL)
        updated_seat_price = 470.00
        self.seat_dict['price'] = updated_seat_price
        self.seat_dict['type'] = Seat.VERIFIED
        self.assertNotEqual(self.seat.price, updated_seat_price)

        response = self.client.post(
            reverse('publisher:publisher_seats_edit', kwargs={'pk': self.seat.id}),
            self.seat_dict
        )

        # verify that non staff user can't update course seat without permission
        self.assertEqual(response.status_code, 403)

        # assign user a group and assign organization to the course
        group_organization_1 = factories.GroupOrganizationFactory(group=group)
        non_staff_user.groups.add(group_organization_1.group)
        self.seat.course_run.course.organizations.add(group_organization_1.organization)

        response = self.client.post(
            reverse('publisher:publisher_seats_edit', kwargs={'pk': self.seat.id}),
            self.seat_dict
        )

        self.assertRedirects(
            response,
            expected_url=reverse('publisher:publisher_seats_edit', kwargs={'pk': self.seat.id}),
            status_code=302,
            target_status_code=200
        )

        seat = Seat.objects.get(id=self.seat.id)
        # Assert that seat is updated.
        self.assertEqual(seat.price, updated_seat_price)
        self.assertEqual(seat.type, Seat.VERIFIED)

        self.seat_dict['type'] = Seat.HONOR
        response = self.client.post(
            reverse('publisher:publisher_seats_edit', kwargs={'pk': self.seat.id}),
            self.seat_dict
        )
        seat = Seat.objects.get(id=self.seat.id)
        # Assert that we can change seat type.
        self.assertEqual(seat.type, Seat.HONOR)

        self.assertRedirects(
            response,
            expected_url=reverse('publisher:publisher_seats_edit', kwargs={'pk': self.seat.id}),
            status_code=302,
            target_status_code=200
        )


@ddt.ddt
class CourseRunDetailTests(TestCase):
    """ Tests for the course-run detail view. """

    def setUp(self):
        super(CourseRunDetailTests, self).setUp()
        self.course = factories.CourseFactory()
        self.user = UserFactory(is_staff=True)
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.course_run = factories.CourseRunFactory(course=self.course)
        self._generate_seats([Seat.AUDIT, Seat.HONOR, Seat.VERIFIED, Seat.PROFESSIONAL])
        self._generate_credit_seat()
        self.page_url = reverse('publisher:publisher_course_run_detail', args=[self.course_run.id])
        self.wrapped_course_run = CourseRunWrapper(self.course_run)
        self.date_format = '%b %d, %Y, %H:%M:%S %p'

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

    def test_page_without_data_staff(self):
        """ Verify that staff user can access detail page without any data
        available for that course-run.
        """
        course_run = factories.CourseRunFactory(course=self.course)
        page_url = reverse('publisher:publisher_course_run_detail', args=[course_run.id])
        response = self.client.get(page_url)
        self.assertEqual(response.status_code, 200)

    def test_page_with_invalid_id(self):
        """ Verify that invalid course run id return 404. """
        page_url = reverse('publisher:publisher_course_run_detail', args=[3434])
        response = self.client.get(page_url)
        self.assertEqual(response.status_code, 404)

    def test_details_page_non_staff(self):
        """ Verify that non staff user can't access detail page. """
        non_staff_user, group = create_non_staff_user_and_login(self)

        response = self.client.get(self.page_url)
        self.assertEqual(response.status_code, 403)

        group_organization = factories.GroupOrganizationFactory(group=group)
        # assign user a group and assign view permission on that group
        non_staff_user.groups.add(group)

        self.course.organizations.add(group_organization.organization)

        response = self.client.get(self.page_url)

        self.assertEqual(response.status_code, 200)

    def _generate_seats(self, modes):
        """ Helper method to add seats for a course-run. """
        for mode in modes:
            factories.SeatFactory(type=mode, course_run=self.course_run)

    def _generate_credit_seat(self):
        """ Helper method to add credit seat for a course-run. """
        factories.SeatFactory(type='credit', course_run=self.course_run, credit_provider='ASU', credit_hours=9)

    def test_course_run_detail_page_staff(self):
        """ Verify that detail page contains all the data for drupal, studio and
        cat with staff user.
        """
        response = self.client.get(self.page_url)
        self.assertEqual(response.status_code, 200)
        self._assert_credits_seats(response, self.wrapped_course_run.credit_seat)
        self._assert_non_credits_seats(response, self.wrapped_course_run.non_credit_seats)
        self._assert_studio_fields(response)
        self._assert_cat(response)
        self._assert_drupal(response)
        self._assert_subjects(response)

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
        self.assertContains(response, 'Seat Type')
        self.assertContains(response, 'Price')
        self.assertContains(response, 'Currency')
        self.assertContains(response, 'Upgrade Deadline')

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
            'Title', 'Number', 'Course ID', 'Price', 'Sub Title', 'School', 'Subject', 'XSeries',
            'Start Date', 'End Date', 'Self Paced', 'Staff', 'Estimated Effort', 'Languages',
            'Video Translations', 'Level', 'About this Course', "What you'll learn",
            'Prerequisite', 'Keywords', 'Sponsors', 'Enrollments'
        ]
        for field in fields:
            self.assertContains(response, field)

        values = [
            self.wrapped_course_run.title, self.wrapped_course_run.lms_course_id,
            self.wrapped_course_run.verified_seat_price, self.wrapped_course_run.short_description,
            self.wrapped_course_run.xseries_name, self.wrapped_course_run.min_effort,
            self.wrapped_course_run.pacing_type, self.wrapped_course_run.persons,
            self.wrapped_course_run.max_effort, self.wrapped_course_run.language.name,
            self.wrapped_course_run.video_languages, self.wrapped_course_run.level_type,
            self.wrapped_course_run.full_description, self.wrapped_course_run.expected_learnings,
            self.wrapped_course_run.prerequisites, self.wrapped_course_run.keywords
        ]
        for value in values:
            self.assertContains(response, value)

        for seat in self.wrapped_course_run.wrapped_obj.seats.all():
            self.assertContains(response, seat.type)

    def _assert_cat(self, response):
        """ Helper method to test cat data. """
        fields = [
            'Course ID', 'Course Type'
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

    def _assert_subjects(self, response):
        """ Helper method to test course subjects. """
        for subject in self.wrapped_course_run.subjects:
            self.assertContains(response, subject.name)

    def test_detail_page_with_comments(self):
        """ Verify that detail page contains all the data along with comments
        for course.
        """
        user = UserFactory(is_staff=True, is_superuser=True)
        site = Site.objects.get(pk=settings.SITE_ID)

        comment = CommentFactory(content_object=self.course, user=user, site=site)
        response = self.client.get(self.page_url)
        self.assertEqual(response.status_code, 200)
        self._assert_credits_seats(response, self.wrapped_course_run.credit_seat)
        self._assert_non_credits_seats(response, self.wrapped_course_run.non_credit_seats)
        self._assert_studio_fields(response)
        self._assert_cat(response)
        self._assert_drupal(response)
        self._assert_subjects(response)
        self.assertContains(response, 'Total Comments 1')
        self.assertContains(response, comment.comment)

    def test_get_course_return_none(self):
        """ Verify that `ViewPermissionMixin.get_course` return none
        if `publisher_object` doesn't have `course` attr.
        """
        non_staff_user, group = create_non_staff_user_and_login(self)   # pylint: disable=unused-variable
        page_url = reverse('publisher:publisher_course_run_detail', args=[self.course_run.id])
        with patch.object(CourseRunDetailView, 'get_object', return_value=non_staff_user):
            response = self.client.get(page_url)
            self.assertEqual(response.status_code, 403)


class ChangeStateViewTests(TestCase):
    """ Tests for the `ChangeStateView`. """

    def setUp(self):
        super(ChangeStateViewTests, self).setUp()
        self.course = factories.CourseFactory()
        self.user = UserFactory(is_staff=True)
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.course_run = factories.CourseRunFactory(course=self.course)
        self.page_url = reverse('publisher:publisher_course_run_detail', args=[self.course_run.id])
        self.change_state_url = reverse('publisher:publisher_change_state', args=[self.course_run.id])

    def test_page_without_login(self):
        """ Verify that user can't access change state endpoint when not logged in. """
        self.client.logout()
        response = self.client.post(self.change_state_url, data={'state': State.NEEDS_REVIEW})

        self.assertRedirects(
            response,
            expected_url='{url}?next={next}'.format(
                url=reverse('login'),
                next=self.change_state_url
            ),
            status_code=302,
            target_status_code=302
        )

    def test_change_state_with_staff(self):
        """ Verify that staff user can change workflow state from detail page. """
        response = self.client.get(self.page_url)
        self.assertContains(response, 'Status:')
        self.assertContains(response, State.DRAFT.title())
        # change workflow state from `DRAFT` to `NEEDS_REVIEW`
        response = self.client.post(self.change_state_url, data={'state': State.NEEDS_REVIEW}, follow=True)

        # assert that state is changed to `NEEDS_REVIEW`
        self.assertContains(response, State.NEEDS_REVIEW.title().replace('_', ' '))

    def test_change_state_not_allowed_with_staff(self):
        """ Verify that staff user can't change workflow state from `DRAFT` to `PUBLISHED`. """
        response = self.client.get(self.page_url)
        self.assertContains(response, 'Status:')
        self.assertContains(response, State.DRAFT.title())
        # change workflow state from `DRAFT` to `PUBLISHED`
        response = self.client.post(self.change_state_url, data={'state': State.PUBLISHED}, follow=True)
        # assert that state is not changed to `PUBLISHED`
        self.assertNotContains(response, State.PUBLISHED.title())
        self.assertContains(response, 'There was an error in changing state.')

    def test_change_state_with_no_staff(self):
        """ Tests change state for non staff user. """
        non_staff_user, group = create_non_staff_user_and_login(self)
        response = self.client.post(self.change_state_url, data={'state': State.NEEDS_REVIEW}, follow=True)

        # verify that non staff user can't change workflow state without permission
        self.assertEqual(response.status_code, 403)

        group_organization = factories.GroupOrganizationFactory(group=group)
        # assign user a group and assign view permission on that group
        non_staff_user.groups.add(group)

        self.course.organizations.add(group_organization.organization)

        response = self.client.get(self.page_url)

        self.assertContains(response, 'Status:')
        self.assertContains(response, State.DRAFT.title())
        # change workflow state from `DRAFT` to `NEEDS_REVIEW`
        response = self.client.post(self.change_state_url, data={'state': State.NEEDS_REVIEW}, follow=True)

        # assert that state is changed to `NEEDS_REVIEW`
        self.assertContains(response, State.NEEDS_REVIEW.title().replace('_', ' '))


class DashboardTests(TestCase):
    """ Tests for the `Dashboard`. """

    def setUp(self):
        super(DashboardTests, self).setUp()

        self.user1 = UserFactory()
        self.group_organization_1 = factories.GroupOrganizationFactory()
        self.user1.groups.add(self.group_organization_1.group)

        self.user2 = UserFactory()
        self.group_organization_2 = factories.GroupOrganizationFactory()
        self.user2.groups.add(self.group_organization_2.group)

        self.client.login(username=self.user1.username, password=USER_PASSWORD)
        self.page_url = reverse('publisher:publisher_dashboard')

        # create course and assign an organization
        self.course_run_1 = self._create_assign_organization(State.DRAFT, self.group_organization_1.organization)
        self.course_run_2 = self._create_assign_organization(State.NEEDS_REVIEW, self.group_organization_1.organization)
        self.course_run_3 = self._create_assign_organization(State.PUBLISHED, self.group_organization_1.organization)

        # group-b course
        self._create_assign_organization(State.DRAFT, self.group_organization_2.organization)
        self.table_class = "data-table-{id} display"

    def _create_assign_organization(self, state, organization):
        """ DRY method to create course and assign the permissions"""
        course_run = factories.CourseRunFactory(state=factories.StateFactory(name=state))
        course_run.course.organizations.add(organization)
        return course_run

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

    def test_page_with_different_group_user(self):
        """ Verify that user from one group can access only that group courses. """
        self.client.logout()
        self.client.login(username=self.user2.username, password=USER_PASSWORD)
        self.assert_dashboard_response()

    def test_page_with_staff_user(self):
        """ Verify that staff user can see all tabs with all course runs from all groups. """
        self.client.logout()
        staff_user = UserFactory(is_staff=True)
        self.client.login(username=staff_user.username, password=USER_PASSWORD)
        self.assert_dashboard_response()

    def test_different_course_runs_counts(self):
        """ Verify that user can access published, un-published and
        studio requests course runs. """
        self.assert_dashboard_response()

    def test_studio_request_course_runs(self):
        """ Verify that page loads the list course runs which need studio request. """
        self.course_run_1.lms_course_id = 'test'
        self.course_run_1.save()
        response = self.assert_dashboard_response()
        self.assertContains(response, self.table_class.format(id='studio'))
        self.assertEqual(len(response.context['studio_request_courses']), 1)

    def test_without_studio_request_course_runs(self):
        """ Verify that studio tab indicates a message if no course-run available. """
        self.course_run_1.lms_course_id = 'test'
        self.course_run_1.save()
        self.course_run_2.lms_course_id = 'test-2'
        self.course_run_2.save()
        response = self.assert_dashboard_response()
        self.assertEqual(len(response.context['studio_request_courses']), 0)
        self.assertContains(response, 'There are no course-runs require studio instance.')

    def test_without_published_course_runs(self):
        """ Verify that published tab indicates a message if no course-run available. """
        self.course_run_3.change_state(target=State.DRAFT)
        response = self.assert_dashboard_response()
        self.assertEqual(len(response.context['published_course_runs']), 0)
        self.assertContains(response, "Looks like you haven't published any course yet")

    def test_published_course_runs(self):
        """ Verify that published tab loads course runs list. """
        response = self.assert_dashboard_response()
        self.assertEqual(len(response.context['published_course_runs']), 1)
        self.assertContains(response, self.table_class.format(id='published'))
        self.assertContains(response, 'The list below contains all course runs published in the past 30 days')

    def test_with_preview_ready_course_runs(self):
        """ Verify that preview ready tabs loads the course runs list. """
        self.course_run_2.change_state(target=State.NEEDS_FINAL_APPROVAL)
        self.course_run_2.save()
        response = self.assert_dashboard_response()
        self.assertEqual(len(response.context['preview_course_runs']), 1)
        self.assertContains(response, self.table_class.format(id='preview'))
        self.assertContains(response, 'The list below contains all course runs awaiting course team approval')

    def test_without_preview_ready_course_runs(self):
        """ Verify preview ready tabs shows a message if no course run available. """
        response = self.assert_dashboard_response()
        self.assertEqual(len(response.context['preview_course_runs']), 0)
        self.assertContains(response, 'There are no course runs marked for preview.')

    def test_without_preview_url(self):
        """ Verify preview ready tabs shows a message if no course run available. """
        self.course_run_2.preview_url = None
        self.course_run_2.save()
        response = self.assert_dashboard_response()
        self.assertEqual(len(response.context['preview_course_runs']), 0)
        self.assertContains(response, 'There are no course runs marked for preview.')

    def test_without_in_progress_course_runs(self):
        """ Verify in progress tabs shows a message if no course run available. """
        response = self.assert_dashboard_response()
        self.assertEqual(len(response.context['in_progress_course_runs']), 0)
        self.assertContains(response, 'There are no in progress course runs.')

    def test_with_in_progress_course_runs(self):
        """ Verify that in progress tabs loads the course runs list. """
        self.course_run_2.change_state(target=State.NEEDS_FINAL_APPROVAL)
        self.course_run_2.save()

        response = self.assert_dashboard_response()
        self.assertEqual(len(response.context['in_progress_course_runs']), 1)
        self.assertContains(response, self.table_class.format(id='in-progress'))

    def assert_dashboard_response(self):
        """ Dry method to assert the response."""
        response = self.client.get(self.page_url)
        self.assertEqual(response.status_code, 200)
        return response


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


class UpdateCourseKeyViewTests(TestCase):
    """ Tests for `UpdateCourseKeyView` """

    def setUp(self):
        super(UpdateCourseKeyViewTests, self).setUp()
        self.course_run = factories.CourseRunFactory()
        self.user = UserFactory(is_staff=True, is_superuser=True)

        self.group_organization_1 = factories.GroupOrganizationFactory()

        self.user.groups.add(self.group_organization_1.group)
        # assign_perm(Course.VIEW_PERMISSION, self.group_organization_1.group, self.course_run.course)
        self.course_run.course.organizations.add(self.group_organization_1.organization)

        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.update_course_key_url = reverse(
            'publisher:publisher_course_run_detail', kwargs={'pk': self.course_run.id}
        )

        factories.UserAttributeFactory(user=self.user, enable_email_notification=True)
        toggle_switch('enable_publisher_email_notifications', True)

    def test_update_course_key_with_errors(self):
        """ Test that api returns error with invalid course key."""
        invalid_course_id = 'invalid-course-key'
        response = self.client.patch(
            self.update_course_key_url,
            data=json.dumps({'lms_course_id': invalid_course_id}),
            content_type=JSON_CONTENT_TYPE
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data.get('non_field_errors'), ['Invalid course key [{}]'.format(invalid_course_id)]
        )

    def test_update_course_key(self):
        """ Test that user can update `lms_course_id` for a course run."""
        # Verify that `lms_course_id` and `changed_by` are None
        self.assert_course_key_and_changed_by()

        lms_course_id = 'course-v1:edxTest+TC12+2050Q1'
        response = self.client.patch(
            self.update_course_key_url,
            data=json.dumps({'lms_course_id': lms_course_id}),
            content_type=JSON_CONTENT_TYPE
        )
        self.assertEqual(response.status_code, 200)

        # Verify that `lms_course_id` and `changed_by` are not None
        self.assert_course_key_and_changed_by(lms_course_id=lms_course_id, changed_by=self.user)

        # assert email sent
        self.assert_email_sent(
            reverse('publisher:publisher_course_run_detail', kwargs={'pk': self.course_run.id}),
            'Studio instance created',
            'Studio instance created for the following course run'
        )

    def assert_course_key_and_changed_by(self, lms_course_id=None, changed_by=None):
        self.course_run = CourseRun.objects.get(id=self.course_run.id)

        self.assertEqual(self.course_run.lms_course_id, lms_course_id)
        self.assertEqual(self.course_run.changed_by, changed_by)

    def assert_email_sent(self, object_path, subject, expected_body):
        """ DRY method to assert sent email data"""
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual([settings.PUBLISHER_FROM_EMAIL], mail.outbox[0].to)
        self.assertEqual([self.user.email], mail.outbox[0].bcc)
        self.assertEqual(str(mail.outbox[0].subject), subject)

        body = mail.outbox[0].body.strip()
        self.assertIn(expected_body, body)
        page_url = 'https://{host}{path}'.format(host=Site.objects.get_current().domain.strip('/'), path=object_path)
        self.assertIn(page_url, body)
