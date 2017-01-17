from django.test import TestCase
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from course_discovery.apps.api.pagination import PageNumberPagination, ProxiedPagination


class ProxiedPaginationTests(TestCase):
    def setUp(self):
        super().setUp()

        self.proxied_paginator = ProxiedPagination()
        self.page_number_paginator = PageNumberPagination()
        self.limit_offset_paginator = LimitOffsetPagination()

        self.queryset = range(100)

    def get_request(self, **data):
        """
        Constructs an instance of DRF's internal representation of a Request,
        required for testing in this context.
        """
        factory = APIRequestFactory()
        return Request(factory.get('/', data))

    def paginate_queryset(self, paginator, request):
        return list(paginator.paginate_queryset(self.queryset, request))

    def get_paginated_content(self, paginator, queryset):
        response = paginator.get_paginated_response(queryset)
        return response.data

    def assert_proxied(self, expected_paginator, request):
        proxied_queryset = self.paginate_queryset(self.proxied_paginator, request)
        expected_queryset = self.paginate_queryset(expected_paginator, request)
        self.assertEqual(proxied_queryset, expected_queryset)

        proxied_data = self.get_paginated_content(self.proxied_paginator, proxied_queryset)
        expected_data = self.get_paginated_content(expected_paginator, expected_queryset)
        self.assertEqual(proxied_data, expected_data)

    def test_default_pagination(self):
        """
        Verify that ProxiedPagination behaves like LimitOffsetPagination by
        default, when no query parameters are present.
        """
        request = self.get_request()
        self.assert_proxied(self.limit_offset_paginator, request)

    def test_page_number_pagination(self):
        """
        Verify that ProxiedPagination proxies to PageNumberPagination when a
        `page` query parameter is present.
        """
        request = self.get_request(page=2)
        self.assert_proxied(self.page_number_paginator, request)

    def test_limit_offset_pagination(self):
        """
        Verify that ProxiedPagination proxies to LimitOffsetPagination when a
        `limit` query parameter is present.
        """
        request = self.get_request(limit=2)
        self.assert_proxied(self.limit_offset_paginator, request)

    def test_noncallable_attribute_access(self):
        """
        Verify that attempts to access noncallable attributes are proxied to
        PageNumberPagination and LimitOffsetPagination.
        """
        # Access an attribute unique to PageNumberPagination.
        self.assertEqual(
            self.proxied_paginator.page_query_param,
            self.page_number_paginator.page_query_param
        )

        # Access an attribute unique to LimitOffsetPagination.
        self.assertEqual(
            self.proxied_paginator.limit_query_param,
            self.limit_offset_paginator.limit_query_param
        )

        # Access an attribute common to both PageNumberPagination and LimitOffsetPagination.
        self.assertEqual(
            self.proxied_paginator.display_page_controls,
            self.limit_offset_paginator.display_page_controls
        )

        # Access an attribute found on neither PageNumberPagination nor LimitOffsetPagination.
        with self.assertRaises(AttributeError):
            zach = self.proxied_paginator
            zach.cool  # pylint: disable=pointless-statement
