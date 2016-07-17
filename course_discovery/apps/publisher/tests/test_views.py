"""
Tests for publisher views.
"""
import ddt

from django.core.urlresolvers import reverse
from django.test import TestCase

from course_discovery.apps.publisher.models import Status
from course_discovery.apps.publisher.tests import toggle_switch
from course_discovery.apps.publisher.tests import factories


# pylint: disable=no-member

@ddt.ddt
class UnpublishedCourseRunListing(TestCase):
    """ Tests cases for non-published course run lists view. """

    def setUp(self):
        super(UnpublishedCourseRunListing, self).setUp()
        toggle_switch('enable_publisher', True)
        self.course_run = factories.CourseRunFactory()
        self.course_run_status = factories.StatusFactory(
            course_run=self.course_run, name=Status.PUBLISHED
        )
        self.course_detail = factories.CourseRunDetailFactory(
            course_run=self.course_run, target_content=True, priority=False
        )
        self.listing_path = self._course_listing_url()
        self.date_time_format = '%Y-%m-%d %H:%M:%S'

    def _course_listing_url(self):
        """ Helper method to generate the url for a course listing page."""
        return reverse('publisher:unpublished_courses')

    def test_page_without_enabling_switch(self):
        """ Verify that the course listing view returns 404 if switch
        is not enable. """
        toggle_switch('enable_publisher', False)
        response = self.client.get(self.listing_path)
        self.assertEqual(response.status_code, 404)

    def test_courses_list_with_published_status(self):
        """ Verify that no data will appear on page is status is published. """
        response = self.client.get(self.listing_path)
        self.assertContains(response, 'No Data available')

    @ddt.data(Status.REVIEW, Status.DRAFT)
    def test_courses_list_page(self, status_name):
        """ Verify that the course listing page shows unpublished data. """
        self.course_run_status.name = status_name
        self.course_run_status.save()
        response = self.client.get(self.listing_path)
        self._assert_un_published_data(response)

    def _assert_un_published_data(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.course_run.course.key)
        self.assertContains(response, self.course_run.status.name)

        self.assertContains(response, self.course_run.status.created.strftime(self.date_time_format))
        self.assertContains(response, self.course_run.status.modified.strftime(self.date_time_format))

        self.assertContains(response, self.course_run.detail.priority)
        self.assertContains(response, self.course_run.detail.target_content)
        self.assertContains(response, self.course_run.detail.priority)
