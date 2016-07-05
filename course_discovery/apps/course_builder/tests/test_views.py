"""
Tests for course builder views.
"""
from django.core.urlresolvers import reverse
from django.test import TestCase


class CourseListing(TestCase):
    """ Course builder list view tests. """

    def setUp(self):
        super(CourseListing, self).setUp()
        self.listing_path = self._course_listing_url()

    def _course_listing_url(self):
        """ Helper method to generate the url for a course listing page."""
        return reverse('course_builder:courses_list')

    def test_courses_list_page(self):
        """ Verify that the course listing view renders a page. """
        response = self.client.get(self.listing_path)
        self.assertEqual(response.status_code, 200)
