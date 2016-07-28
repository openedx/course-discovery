# pylint: disable=no-member
from django.test import TestCase
from django.core.urlresolvers import reverse

from course_discovery.apps.publisher.tests import factories
from course_discovery.apps.course_metadata.models import Seat
from course_discovery.apps.publisher.wrappers import CourseRunWrapper


class PrePublishViewTests(TestCase):
    """ Tests for the pre-publish view. """

    def setUp(self):
        super(PrePublishViewTests, self).setUp()
        self.course = factories.CourseFactory()
        self.course_run = factories.CourseRunFactory(course=self.course)
        self._generate_seats()
        self.page_url = reverse('publisher:pre_publisher', args=[self.course_run.id])
        self.wrapper_object = CourseRunWrapper(self.course_run)

    def _generate_seats(self):
        factories.SeatFactory(type='honor', course_run=self.course_run)
        factories.SeatFactory(type='audit', course_run=self.course_run)
        factories.SeatFactory(type='verified', course_run=self.course_run)
        factories.SeatFactory(type='credit', course_run=self.course_run, credit_provider='ASU', credit_hours=9)
        factories.SeatFactory(type='credit', course_run=self.course_run, credit_provider='Hogwarts', credit_hours=4)

    def test_pre_publish_page(self):
        response = self.client.get(self.page_url)
        self.assertEqual(response.status_code, 200)
        self._assert_credits_seats(response, self.wrapper_object.credit_seats)
        self._assert_non_credits_seats(response, self.wrapper_object.non_credit_seats)

    def _assert_html(self, response):
        self.assertContains(response, 'test-org',)

    def _assert_credits_seats(self, response, seats):
        self.assertContains(response, 'Credit Seats')
        self.assertContains(response, 'Credit Provider')
        self.assertContains(response, 'Price')
        self.assertContains(response, 'Currency')
        self.assertContains(response, 'Credit Hours')
        # self.assertContains(response, 'Upgrade Deadline')

        for seat in seats:
            self.assertContains(response, seat.credit_provider)
            self.assertContains(response, seat.price)
            self.assertContains(response, seat.currency)
            self.assertContains(response, seat.credit_hours)
            self.assertContains(response, seat.upgrade_deadline)

    def _assert_non_credits_seats(self, response, seats):
        self.assertContains(response, 'Seat Type')
        self.assertContains(response, 'Price')
        self.assertContains(response, 'Currency')
        self.assertContains(response, 'Upgrade Deadline')

        for seat in seats:
            self.assertContains(response, seat.type)
            self.assertContains(response, seat.price)
            self.assertContains(response, seat.currency)
            # self.assertContains(response, seat.upgrade_deadline)
