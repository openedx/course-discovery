import ddt
import mock
from django.test import TestCase

from course_discovery.apps.api.utils import cast2int

LOGGER_PATH = 'course_discovery.apps.api.utils.logger.exception'


@ddt.ddt
class Cast2IntTests(TestCase):
    name = 'foo'

    @ddt.data(
        ('0', 0),
        ('1', 1),
        (None, None),
    )
    @ddt.unpack
    def test_cast_success(self, value, expected):
        self.assertEqual(cast2int(value, self.name), expected)

    @ddt.data('beep', '1.1')
    def test_cast_failure(self, value):
        with mock.patch(LOGGER_PATH) as mock_logger:
            with self.assertRaises(ValueError):
                cast2int(value, self.name)

        self.assertTrue(mock_logger.called)
