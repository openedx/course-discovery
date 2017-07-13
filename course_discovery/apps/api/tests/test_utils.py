import ddt
import mock
from django.test import TestCase
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from course_discovery.apps.api.utils import cast2int, get_query_param

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


class TestGetQueryParam:
    def test_with_request(self):
        factory = APIRequestFactory()
        request = Request(factory.get('/?q=1'))

        assert get_query_param(request, 'q') == 1

    def test_without_request(self):
        assert get_query_param(None, 'q') is None
