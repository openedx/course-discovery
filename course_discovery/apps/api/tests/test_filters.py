import ddt
from django.test import TestCase
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from course_discovery.apps.api.filters import HaystackRequestFilterMixin


@ddt.ddt
class HaystackRequestFilterMixinTests(TestCase):
    def test_get_request_filters(self):
        """ Verify the method removes query parameters with empty values """
        request = APIRequestFactory().get('/?q=')
        request = APIView().initialize_request(request)
        filters = HaystackRequestFilterMixin.get_request_filters(request)
        self.assertDictEqual(filters, {})
