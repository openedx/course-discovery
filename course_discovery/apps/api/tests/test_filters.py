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

    def test_get_request_filters_with_list(self):
        """ Verify the method does not affect list values. """
        request = APIRequestFactory().get('/?q=&content_type=courserun&content_type=program')
        request = APIView().initialize_request(request)
        filters = HaystackRequestFilterMixin.get_request_filters(request)
        self.assertNotIn('q', filters)
        self.assertEqual(filters.getlist('content_type'), ['courserun', 'program'])

    def test_get_request_filters_with_falsey_values(self):
        """ Verify the method does not strip valid falsey values. """
        request = APIRequestFactory().get('/?q=&test=0')
        request = APIView().initialize_request(request)
        filters = HaystackRequestFilterMixin.get_request_filters(request)
        self.assertNotIn('q', filters)
        self.assertEqual(filters.get('test'), '0')
