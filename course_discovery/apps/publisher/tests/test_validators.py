import ddt
from django.core.exceptions import ValidationError
from django.test import TestCase

from course_discovery.apps.publisher.validators import validate_text_count


@ddt.ddt
class ValidatorTests(TestCase):
    """
    Tests for form validators
    """
    @ddt.data(
        ('<strong>MODULE 0:&nbsp;</strong>', 'MODULE 0:'),
        ('   <strong>MODULE 0: </strong>  ', 'MODULE 0:'),
        ('\n\n<strong>MODULE 0: \n\n</strong>\n\n', 'MODULE 0:')
    )
    @ddt.unpack
    def test_validate_text_count(self, text_to_validate, expected_clean_text):
        """Tests that validate text count work as expected"""
        max_length_allowed = len(expected_clean_text)
        validate_text_count(max_length_allowed)(text_to_validate)

        # Verify you get a Validation Error if try go below the max.
        with self.assertRaises(ValidationError):
            validate_text_count(max_length_allowed - 1)(text_to_validate)
