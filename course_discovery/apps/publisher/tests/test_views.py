import ddt

from django.core.urlresolvers import reverse
from django.forms import model_to_dict
from django.test import TestCase

from course_discovery.apps.publisher.models import Course, CourseRun, Seat
from course_discovery.apps.publisher.tests import factories
from course_discovery.apps.publisher.wrappers import CourseRunWrapper


class CreateUpdateCourseViewTests(TestCase):
    """ Tests for the publisher `CreateCourseView` and `UpdateCourseView`. """

    def setUp(self):
        super(CreateUpdateCourseViewTests, self).setUp()
        self.course = factories.CourseFactory()

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

    def test_update_course(self):
        """ Verify that we can update an existing course. """
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

    def test_update_course_run(self):
        """ Verify that we can update an existing course run. """
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


class SeatsCreateUpdateViewTests(TestCase):
    """ Tests for the publisher `CreateSeatView` and `UpdateSeatView`. """

    def setUp(self):
        super(SeatsCreateUpdateViewTests, self).setUp()
        self.seat = factories.SeatFactory(type=Seat.PROFESSIONAL, credit_hours=0)
        self.seat_dict = model_to_dict(self.seat)
        self.seat_dict.pop('upgrade_deadline')

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

    def test_update_seat(self):
        """ Verify that we can update an existing seat. """
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
        # Assert that we change seat type.
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
        self.course_run = factories.CourseRunFactory(course=self.course)
        self._generate_seats([Seat.AUDIT, Seat.HONOR, Seat.VERIFIED, Seat.PROFESSIONAL])
        self._generate_credit_seat()
        self.page_url = reverse('publisher:publisher_course_run_detail', args=[self.course_run.id])
        self.wrapped_course_run = CourseRunWrapper(self.course_run)
        self.date_format = '%b %d, %Y, %H:%M:%S %p'

    def test_page_without_data(self):
        """ Verify that detail page without any data available for that course-run. """
        course_run = factories.CourseRunFactory(course=self.course)
        page_url = reverse('publisher:publisher_course_run_detail', args=[course_run.id])
        response = self.client.get(page_url)
        self.assertEqual(response.status_code, 200)

    def _generate_seats(self, modes):
        """ Helper method to add seats for a course-run. """
        for mode in modes:
            factories.SeatFactory(type=mode, course_run=self.course_run)

    def _generate_credit_seat(self):
        """ Helper method to add credit seat for a course-run. """
        factories.SeatFactory(type='credit', course_run=self.course_run, credit_provider='ASU', credit_hours=9)

    def test_course_run_detail_page(self):
        """ Verify that detail page contains all the data for drupal, studio and
        cat.
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
