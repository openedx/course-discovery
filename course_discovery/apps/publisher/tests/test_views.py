import ddt
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.urlresolvers import reverse
from django.forms import model_to_dict
from django.test import TestCase
from guardian.shortcuts import assign_perm

from course_discovery.apps.core.tests.factories import UserFactory, USER_PASSWORD
from course_discovery.apps.publisher.models import Course, CourseRun, Seat, State
from course_discovery.apps.publisher.tests import factories
from course_discovery.apps.publisher.wrappers import CourseRunWrapper
from course_discovery.apps.publisher_comments.tests.factories import CommentFactory


class CreateUpdateCourseViewTests(TestCase):
    """ Tests for the publisher `CreateCourseView` and `UpdateCourseView`. """

    def setUp(self):
        super(CreateUpdateCourseViewTests, self).setUp()
        self.course = factories.CourseFactory()
        self.group = factories.GroupFactory()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.user.groups.add(self.group)
        self.site = Site.objects.get(pk=settings.SITE_ID)
        self.client.login(username=self.user.username, password=USER_PASSWORD)

    def test_create_course(self):
        """ Verify that we can create a new course. """
        # Create unique course number
        course_number = '{}.1.456'.format(self.course.number)
        course_dict = model_to_dict(self.course)
        course_dict['number'] = course_number
        response = self.client.post(reverse('publisher:publisher_courses_new'), course_dict)

        course = Course.objects.get(number=course_number)
        self.assertRedirects(
            response,
            expected_url=reverse('publisher:publisher_courses_edit', kwargs={'pk': course.id}),
            status_code=302,
            target_status_code=200
        )

        self.assertEqual(course.number, course_number)
        self.assertTrue(self.user.has_perm(Course.VIEW_PERMISSION, course))
        response = self.client.get(reverse('publisher:publisher_courses_new'))
        self.assertNotContains(response, 'Add new comment')
        self.assertNotContains(response, 'Total Comments')

    def test_update_course_with_staff(self):
        """ Verify that staff user can update an existing course. """
        course_dict = model_to_dict(self.course)
        updated_course_title = 'Updated {}'.format(self.course.title)
        course_dict['title'] = updated_course_title
        self.assertNotEqual(self.course.title, updated_course_title)
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

    def test_course_edit_page_with_non_staff(self):
        """ Verify that non staff user can't access course edit page without permission. """
        non_staff_user = UserFactory()
        group = factories.GroupFactory()

        self.client.logout()
        self.client.login(username=non_staff_user.username, password=USER_PASSWORD)

        course_dict = model_to_dict(self.course)
        updated_course_title = 'Updated {}'.format(self.course.title)
        course_dict['title'] = updated_course_title
        self.assertNotEqual(self.course.title, updated_course_title)
        response = self.client.get(
            reverse('publisher:publisher_courses_edit', kwargs={'pk': self.course.id})
        )

        self.assertEqual(response.status_code, 403)

        # assign user a group and assign view permission on that group
        non_staff_user.groups.add(group)
        assign_perm(Course.VIEW_PERMISSION, group, self.course)

        response = self.client.get(
            reverse('publisher:publisher_courses_edit', kwargs={'pk': self.course.id})
        )

        self.assertEqual(response.status_code, 200)

    def test_update_course_with_non_staff(self):
        """ Tests for update course with non staff user. """
        non_staff_user = UserFactory()
        group = factories.GroupFactory()

        self.client.logout()
        self.client.login(username=non_staff_user.username, password=USER_PASSWORD)

        course_dict = model_to_dict(self.course)
        updated_course_title = 'Updated {}'.format(self.course.title)
        course_dict['title'] = updated_course_title
        self.assertNotEqual(self.course.title, updated_course_title)
        response = self.client.post(
            reverse('publisher:publisher_courses_edit', kwargs={'pk': self.course.id}),
            course_dict
        )

        # verify that non staff user can't update course without permission
        self.assertEqual(response.status_code, 403)

        # assign user a group and assign view permission on that group
        non_staff_user.groups.add(group)
        assign_perm(Course.VIEW_PERMISSION, group, self.course)

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


class CreateUpdateCourseRunViewTests(TestCase):
    """ Tests for the publisher `CreateCourseRunView` and `UpdateCourseRunView`. """

    def setUp(self):
        super(CreateUpdateCourseRunViewTests, self).setUp()
        self.course_run = factories.CourseRunFactory()
        self.course_run_dict = model_to_dict(self.course_run)
        self._pop_valuse_from_dict(
            self.course_run_dict,
            ['start', 'end', 'enrollment_start', 'enrollment_end', 'priority', 'certificate_generation']
        )
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.site = Site.objects.get(pk=settings.SITE_ID)
        self.client.login(username=self.user.username, password=USER_PASSWORD)

    def _pop_valuse_from_dict(self, data_dict, key_list):
        for key in key_list:
            data_dict.pop(key)

    def test_create_course_run(self):
        """ Verify that we can create a new course run. """
        lms_course_id = 'course-v1:testX+AS12131+2016_q4'
        self.course_run_dict['lms_course_id'] = lms_course_id
        response = self.client.post(reverse('publisher:publisher_course_runs_new'), self.course_run_dict)

        course_run = CourseRun.objects.get(course=self.course_run.course, lms_course_id=lms_course_id)
        self.assertRedirects(
            response,
            expected_url=reverse('publisher:publisher_course_runs_edit', kwargs={'pk': course_run.id}),
            status_code=302,
            target_status_code=200
        )

        self.assertEqual(course_run.lms_course_id, lms_course_id)

        response = self.client.get(reverse('publisher:publisher_course_runs_new'))
        self.assertNotContains(response, 'Add new comment')
        self.assertNotContains(response, 'Total Comments')

    def test_update_course_run_with_staff(self):
        """ Verify that staff user can update an existing course run. """
        updated_lms_course_id = 'course-v1:testX+AS121+2018_q1'
        self.course_run_dict['lms_course_id'] = updated_lms_course_id
        self.assertNotEqual(self.course_run.lms_course_id, updated_lms_course_id)
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

    def test_edit_course_run_page_with_non_staff(self):
        """ Verify that non staff user can't access course run edit page without permission. """
        non_staff_user = UserFactory()
        group = factories.GroupFactory()

        self.client.logout()
        self.client.login(username=non_staff_user.username, password=USER_PASSWORD)

        updated_lms_course_id = 'course-v1:testX+AS121+2018_q1'
        self.course_run_dict['lms_course_id'] = updated_lms_course_id
        self.assertNotEqual(self.course_run.lms_course_id, updated_lms_course_id)

        response = self.client.get(
            reverse('publisher:publisher_course_runs_edit', kwargs={'pk': self.course_run.id})
        )

        self.assertEqual(response.status_code, 403)

        # assign user a group and assign view permission on that group
        non_staff_user.groups.add(group)
        assign_perm(Course.VIEW_PERMISSION, group, self.course_run.course)

        response = self.client.get(
            reverse('publisher:publisher_course_runs_edit', kwargs={'pk': self.course_run.id})
        )

        self.assertEqual(response.status_code, 200)

    def test_update_course_run_with_non_staff(self):
        """ Test for course run with non staff user. """
        non_staff_user = UserFactory()
        group = factories.GroupFactory()

        self.client.logout()
        self.client.login(username=non_staff_user.username, password=USER_PASSWORD)

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
        non_staff_user.groups.add(group)
        assign_perm(Course.VIEW_PERMISSION, group, self.course_run.course)

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
        non_staff_user = UserFactory()
        group = factories.GroupFactory()

        self.client.logout()
        self.client.login(username=non_staff_user.username, password=USER_PASSWORD)
        response = self.client.get(reverse('publisher:publisher_seats_edit', kwargs={'pk': self.seat.id}))

        self.assertEqual(response.status_code, 403)

        # assign user a group and assign view permission on that group
        non_staff_user.groups.add(group)
        assign_perm(Course.VIEW_PERMISSION, group, self.seat.course_run.course)
        response = self.client.get(reverse('publisher:publisher_seats_edit', kwargs={'pk': self.seat.id}))

        self.assertEqual(response.status_code, 200)

    def test_update_seat_with_non_staff(self):
        """ Tests update seat for non staff user. """
        non_staff_user = UserFactory()
        group = factories.GroupFactory()

        self.client.logout()
        self.client.login(username=non_staff_user.username, password=USER_PASSWORD)

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

        # assign user a group and assign view permission on that group
        non_staff_user.groups.add(group)
        assign_perm(Course.VIEW_PERMISSION, group, self.seat.course_run.course)

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

    def test_page_without_data_staff(self):
        """ Verify that staff user can access detail page without any data
        available for that course-run.
        """
        course_run = factories.CourseRunFactory(course=self.course)
        page_url = reverse('publisher:publisher_course_run_detail', args=[course_run.id])
        response = self.client.get(page_url)
        self.assertEqual(response.status_code, 200)

    def test_details_page_non_staff(self):
        """ Verify that non staff user can't access detail page. """
        non_staff_user = UserFactory()
        group = factories.GroupFactory()

        self.client.logout()
        self.client.login(username=non_staff_user.username, password=USER_PASSWORD)

        response = self.client.get(self.page_url)
        self.assertEqual(response.status_code, 403)

        non_staff_user.groups.add(group)
        assign_perm(Course.VIEW_PERMISSION, group, self.course)

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
        for value in [
            self.course_run.start, self.course_run.end,
            self.course_run.enrollment_start, self.course_run.enrollment_end
        ]:
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
        non_staff_user = UserFactory()
        group = factories.GroupFactory()

        self.client.logout()
        self.client.login(username=non_staff_user.username, password=USER_PASSWORD)
        response = self.client.post(self.change_state_url, data={'state': State.NEEDS_REVIEW}, follow=True)

        # verify that non staff user can't change workflow state without permission
        self.assertEqual(response.status_code, 403)

        # assign user a group and assign view permission on that group
        non_staff_user.groups.add(group)
        assign_perm(Course.VIEW_PERMISSION, group, self.course)
        response = self.client.get(self.page_url)

        self.assertContains(response, 'Status:')
        self.assertContains(response, State.DRAFT.title())
        # change workflow state from `DRAFT` to `NEEDS_REVIEW`
        response = self.client.post(self.change_state_url, data={'state': State.NEEDS_REVIEW}, follow=True)

        # assert that state is changed to `NEEDS_REVIEW`
        self.assertContains(response, State.NEEDS_REVIEW.title().replace('_', ' '))
