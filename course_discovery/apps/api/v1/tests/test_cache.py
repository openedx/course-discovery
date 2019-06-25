import zlib

from django.core.cache import cache
from django.test import TestCase
from rest_framework import permissions, views
from rest_framework.renderers import BrowsableAPIRenderer, JSONRenderer
from rest_framework.response import Response
from rest_framework_extensions.test import APIRequestFactory

from course_discovery.apps.api.cache import compressed_cache_response

factory = APIRequestFactory()


class CompressedCacheResponseTest(TestCase):
    def setUp(self):
        super(CompressedCacheResponseTest, self).setUp()
        self.request = factory.get('')
        self.cache_response_key = 'cache_response_key'

    def test_should_handle_getting_uncompressed_response_from_cache(self):
        """ Verify that the decorator correctly returns uncompressed responses """
        def key_func(**kwargs):  # pylint: disable=unused-argument
            return self.cache_response_key

        class TestView(views.APIView):
            permission_classes = [permissions.AllowAny]
            renderer_classes = [JSONRenderer]

            @compressed_cache_response(key_func=key_func)
            def get(self, request, *args, **kwargs):
                return Response('test response')

        view_instance = TestView()
        view_instance.headers = {}  # pylint: disable=attribute-defined-outside-init
        uncompressed_cached_response = Response('cached test response')
        view_instance.finalize_response(request=self.request, response=uncompressed_cached_response)
        uncompressed_cached_response.render()
        cache.set(self.cache_response_key, uncompressed_cached_response)

        response = view_instance.dispatch(request=self.request)
        self.assertEqual(response.content.decode('utf-8'), '"cached test response"')

    def test_should_handle_getting_compressed_response_from_cache(self):
        """ Verify that the decorator correctly returns compressed responses """
        def key_func(**kwargs):  # pylint: disable=unused-argument
            return self.cache_response_key

        class TestView(views.APIView):
            permission_classes = [permissions.AllowAny]
            renderer_classes = [JSONRenderer]

            @compressed_cache_response(key_func=key_func)
            def get(self, request, *args, **kwargs):
                return Response('test response')

        view_instance = TestView()
        view_instance.headers = {}  # pylint: disable=attribute-defined-outside-init
        compressed_cached_response = Response('compressed cached test response')
        view_instance.finalize_response(request=self.request, response=compressed_cached_response)
        compressed_cached_response.render()

        # Data is encoded and compressed before response goes into the cache
        compressed_cached_response.data = zlib.compress(compressed_cached_response.data.encode('utf-8'))
        cache.set(
            self.cache_response_key,
            compressed_cached_response,
        )

        response = view_instance.dispatch(request=self.request)
        self.assertEqual(response.content.decode('utf-8'), '"compressed cached test response"')

    def test_should_not_cache_for_non_json_responses(self):
        """ Verify that the decorator does not cache if the response is not json """
        def key_func(**kwargs):  # pylint: disable=unused-argument
            return 'non_json_cache_key'

        class TestView(views.APIView):
            permission_classes = [permissions.AllowAny]
            renderer_classes = [BrowsableAPIRenderer]  # Non-json responses

            @compressed_cache_response(key_func=key_func)
            def get(self, request, *args, **kwargs):
                return Response('test response')

        view_instance = TestView()
        view_instance.headers = {}  # pylint: disable=attribute-defined-outside-init
        view_instance.dispatch(request=self.request)

        # Verify nothing was cached
        self.assertEqual(cache.get('non_json_cache_key'), None)
