
from django.core.urlresolvers import reverse
from django.forms import model_to_dict
from django.test import TestCase

from course_discovery.apps.publisher.models import Course, CourseRun, Seat
from course_discovery.apps.publisher.tests import factories


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
