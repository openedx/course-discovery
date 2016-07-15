"""
Tests for course builder views.
"""
from django.core.urlresolvers import reverse
from django.test import TestCase

from course_discovery.apps.publisher.tests import toggle_switch


class CourseListing(TestCase):
    """ Course builder list view tests. """

    def setUp(self):
        super(CourseListing, self).setUp()
        self.listing_path = self._course_listing_url()

    def _course_listing_url(self):
        """ Helper method to generate the url for a course listing page."""
        return reverse('publisher:unpublished_courses')

    def test_courses_list_page(self):
        """ Verify that the course listing view renders a page. """

        # Method should return a 404 if the switch is inactive
        toggle_switch('enable_publisher', False)
        response = self.client.get(self.listing_path)
        self.assertEqual(response.status_code, 404)

        toggle_switch('enable_publisher', True)
        response = self.client.get(self.listing_path)
        self.assertEqual(response.status_code, 200)
