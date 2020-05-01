import logging
import pickle
import time
import zlib

from django.conf import settings
from django.core.cache import cache
from django.http.response import HttpResponse
from rest_framework.renderers import JSONRenderer
from rest_framework_extensions.cache.decorators import CacheResponse
from rest_framework_extensions.key_constructor.bits import KeyBitBase, QueryParamsKeyBit
from rest_framework_extensions.key_constructor.constructors import (
    DefaultListKeyConstructor, DefaultObjectKeyConstructor
)

from course_discovery.apps.api.utils import conditional_decorator

logger = logging.getLogger(__name__)
API_TIMESTAMP_KEY = 'api_timestamp'


class ApiTimestampKeyBit(KeyBitBase):
    def get_data(self, **kwargs):  # pylint: disable=arguments-differ
        return cache.get_or_set(API_TIMESTAMP_KEY, time.time, None)


class TimestampedListKeyConstructor(DefaultListKeyConstructor):
    timestamp = ApiTimestampKeyBit()
    # The DefaultListKeyConstructor includes the PaginationKeyBit. While it does
    # subclass QueryParamsKeyBit, it also bypasses logic which includes all query
    # params in the cache key, restricting the set of query params that end up in
    # the cache key to those that are used for page number pagination. This causes
    # cache collisions when other query params are involved. For more, see:
    # https://github.com/chibisov/drf-extensions/blob/master/rest_framework_extensions/key_constructor/bits.py#L48-L49
    querystring = QueryParamsKeyBit()


class TimestampedObjectKeyConstructor(DefaultObjectKeyConstructor):
    timestamp = ApiTimestampKeyBit()
    # The DefaultObjectKeyConstructor doesn't include querystring parameters
    # in its cache key.
    querystring = QueryParamsKeyBit()


def timestamped_list_key_constructor(*args, **kwargs):  # pylint: disable=unused-argument
    return TimestampedListKeyConstructor()(**kwargs)


def timestamped_object_key_constructor(*args, **kwargs):  # pylint: disable=unused-argument
    return TimestampedObjectKeyConstructor()(**kwargs)


def set_api_timestamp():
    timestamp = time.time()
    cache.set(API_TIMESTAMP_KEY, timestamp, None)


def api_change_receiver(sender, **kwargs):  # pylint: disable=unused-argument
    """
    Receiver function for handling post_save and post_delete signals emitted by
    course_metadata models.
    """
    set_api_timestamp()


class CompressedCacheResponse(CacheResponse):
    """
    Subclasses CacheResponse to allow for compression of content going into the cache
    See https://github.com/chibisov/drf-extensions/blob/master/rest_framework_extensions/cache/decorators.py#L52
    for a similar implementation of process_cache_response without compression
    """
    def process_cache_response(self, view_instance, view_method, request, args, kwargs):
        key = self.calculate_key(
            view_instance=view_instance,
            view_method=view_method,
            request=request,
            args=args,
            kwargs=kwargs
        )
        response_triple = self.cache.get(key)
        if view_instance.__class__.__name__ == 'ProgramViewSet':
            if not response_triple or len(response_triple[0]) < 100:
                truncated_response_triple = response_triple
            else:
                truncated_response_triple = (
                    response_triple[0][:100] + "...".encode('ascii'),
                    response_triple[1],
                    response_triple[2]
                )
            logger.info(
                "%r page cache result %r from key %r (request: %r, args: %r, kwargs: %r)",
                view_method,
                truncated_response_triple,
                key,
                request,
                args,
                kwargs
            )

        if not response_triple:
            response = view_method(view_instance, request, *args, **kwargs)
            response = view_instance.finalize_response(request, response, *args, **kwargs)
            response.render()

            if (not (response.status_code >= 400 or self.cache_errors) and
                    isinstance(response.accepted_renderer, JSONRenderer)):
                # Put the response in the cache only if there are no cache errors, response errors,
                # and the format is json. We avoid caching for the BrowsableAPIRenderer so that users don't see
                # different usernames that are cached from the BrowsableAPIRenderer html
                response_triple = (
                    zlib.compress(response.rendered_content),
                    response.status_code,
                    response._headers.copy(),  # pylint: disable=protected-access
                )
                if len(response_triple[0]) > 1.5 * 1024 * 1024:  # This might be over the item size
                    actual_size = len(pickle.dumps(response_triple))
                    if actual_size >= 1.99 * 1024 * 1024:
                        logger.warning(
                            "Cached object for %s is likely over the memcached item size limit (pickle length: %s)",
                            request.get_full_path(),
                            actual_size,
                        )
                self.cache.set(key, response_triple, self.timeout)
        else:
            # If we get data from the cache, we reassemble the data to build a response
            # We reassemble the pieces from the cache because we can't actually set rendered_content
            # which is the part of the response that we compress
            compressed_content, status, headers = response_triple

            try:
                decompressed_content = zlib.decompress(compressed_content)
            except (TypeError, zlib.error):
                # If we get a type error or a zlib error, the response content was never compressed
                decompressed_content = compressed_content

            response = HttpResponse(content=decompressed_content, status=status)
            response._headers = headers  # pylint: disable=protected-access

        if not hasattr(response, '_closable_objects'):
            response._closable_objects = []  # pylint: disable=protected-access

        return response


# Decorator for mixin
compressed_cache_response = CompressedCacheResponse


class CompressedCacheResponseMixin():
    """
    Acts like drf-extensions CacheResponseMixin, but with compression into the cache and decompression out of it
    """
    object_cache_key_func = timestamped_object_key_constructor
    list_cache_key_func = timestamped_list_key_constructor
    object_cache_timeout = settings.REST_FRAMEWORK_EXTENSIONS['DEFAULT_CACHE_RESPONSE_TIMEOUT']
    list_cache_timeout = settings.REST_FRAMEWORK_EXTENSIONS['DEFAULT_CACHE_RESPONSE_TIMEOUT']

    @conditional_decorator(
        settings.USE_API_CACHING,
        compressed_cache_response(key_func=list_cache_key_func, timeout=list_cache_timeout),
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @conditional_decorator(
        settings.USE_API_CACHING,
        compressed_cache_response(key_func=object_cache_key_func, timeout=object_cache_timeout),
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)
