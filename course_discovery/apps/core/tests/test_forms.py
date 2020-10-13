"""Tests for core forms."""
import ddt
from django.test import TestCase

from course_discovery.apps.core.forms import UserThrottleRateForm
from course_discovery.apps.core.tests.factories import UserFactory


@ddt.ddt
class UserThrottleRateFormTest(TestCase):
    """Tests for the UserThrottleRate admin form."""

    def setUp(self):
        super().setUp()
        self.user = UserFactory()

    def test_form_valid(self):
        form = UserThrottleRateForm({'rate': '100/day', 'user': self.user.id})
        self.assertTrue(form.is_valid())

    @ddt.data(
        ('100', ["'rate' must be in the format defined by DRF, such as '100/hour'."]),
        ('100/fortnight', ["period must be one of ('second', 'minute', 'hour', 'day')."]),
        ('foo/day', ["'rate' must be in the format defined by DRF, such as '100/hour'."]),
        (None, ['This field is required.']),
    )
    @ddt.unpack
    def test_form_invalid_rate(self, rate, expected_error):
        form = UserThrottleRateForm({'rate': rate, 'user': self.user.id})
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors, {
            'rate': expected_error
        })
