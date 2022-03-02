"""
Unit tests for utils.
"""

from django.test import TestCase

from course_discovery.apps.course_metadata.data_loaders.tests import mock_data
from course_discovery.apps.course_metadata.data_loaders.utils import (
    format_base64_strings, format_curriculum, format_effort_info, format_faqs, format_testimonials
)


class FormattingTests(TestCase):
    """
    Test Suite for formatting utils
    """

    def test_format_testimonials(self):
        """
        Test the utility function format_testimonials
        """

        output = format_testimonials(mock_data.COURSE_TESTIMONIALS)
        assert output == (
            "<div><p><i>\"Example Testimonial 1\"</i></p><p>-Test User 1 "
            "(Freelance editor and proofreader)</p><p><i>\"Example Testimonial 2\"</i></p><p>-"
            "Test User 2 (Professor, University X)</p></div>"
        )
        assert format_testimonials([]) == ""

    def test_format_faqs(self):
        """
        Test the utility function format_faqs
        """

        output = format_faqs(mock_data.COURSE_FAQS)
        assert output == (
            "<div><p><b>Why take this course?</b></p><p> Example Content with"
            " a <a href=\"https://edx.org\" target=\"_blank\">link</a>.</p><p><b>Is earth flat?"
            "</b></p>Earth is a planet from out solar system</div>"
        )
        assert format_faqs([]) == ""

    def test_format_curriculum(self):
        """
        Test the utility function format_curriculum
        """

        output = format_curriculum(mock_data.COURSE_CURRICULAM)
        assert output == (
            "<div><p>See how will this be represented in html.</p><p><b>Orientation"
            " module: </b>Welcome to your Online Campus</p><p><b>Module 1: </b>Introduction to editing"
            "</p><p><b>Module 2: </b>Spelling, consistency and style</p></div>"
        )
        assert format_faqs({}) == ""

    def test_format_effort_info(self):
        """
        Test the utility function format_effort_info
        """

        output = format_effort_info(mock_data.EFFORT_FORMATS[0])
        assert output == (7, 10)

        output = format_effort_info(mock_data.EFFORT_FORMATS[1])
        assert output == (7, 8)

        # returns None if empty string is passed
        self.assertIsNone(format_effort_info(""))

    def test_format_base64_strings(self):
        """
        Test the utility function format_base64_strings
        """

        output = format_base64_strings(mock_data.BASE64_STRING)
        assert output == "https://www.google.com/"
