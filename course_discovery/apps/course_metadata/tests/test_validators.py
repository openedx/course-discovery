import ddt
from django.core.exceptions import ValidationError
from django.test import TestCase

from course_discovery.apps.course_metadata.validators import validate_html


@ddt.ddt
class TestHtmlValidator(TestCase):
    @ddt.data('', None, '<p>Hello World</p>', '<p>', '<a href="#" rel="noopener">', '<bdo dir="right">')
    def test_valid_html(self, html):
        validate_html(html)

    @ddt.data(
        ('<script>', 'Invalid HTML received: script tag is not allowed'),  # start
        ('</foo>', 'Invalid HTML received: foo tag is not allowed'),  # end
        ("<p onload=''>", 'Invalid HTML received: onload attribute is not allowed on the p tag'),  # attr
        ('<!--comment-->', 'Invalid HTML received'),  # comment
        ('<!DOCTYPE html>', 'Invalid HTML received'),  # decl
        ('<!UNKNOWN>', 'Invalid HTML received'),  # unknown decl
        ('<?proc>', 'Invalid HTML received'),  # processing instruction
    )
    @ddt.unpack
    def test_invalid_html(self, html, msg):
        with self.assertRaises(ValidationError) as cm:
            validate_html(html)
        self.assertEqual(cm.exception.args[0], msg)
