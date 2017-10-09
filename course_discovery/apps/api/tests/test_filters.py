from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from course_discovery.apps.api.filters import HaystackRequestFilterMixin


class TestHaystackRequestFilterMixin:
    def test_get_request_filters(self):
        """ Verify the method removes query parameters with empty values """
        request = APIRequestFactory().get('/?q=')
        request = APIView().initialize_request(request)
        filters = HaystackRequestFilterMixin.get_request_filters(request)
        assert filters == {}

    def test_get_request_filters_with_list(self):
        """ Verify the method does not affect list values. """
        request = APIRequestFactory().get('/?q=&content_type=courserun&content_type=program')
        request = APIView().initialize_request(request)
        filters = HaystackRequestFilterMixin.get_request_filters(request)
        assert 'q' not in filters
        assert filters.getlist('content_type') == ['courserun', 'program']

    def test_get_request_filters_with_falsey_values(self):
        """ Verify the method does not strip valid falsey values. """
        request = APIRequestFactory().get('/?q=&test=0')
        request = APIView().initialize_request(request)
        filters = HaystackRequestFilterMixin.get_request_filters(request)
        assert 'q' not in filters
        assert filters.get('test') == '0'
