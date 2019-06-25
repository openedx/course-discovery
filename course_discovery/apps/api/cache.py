import logging
import time
import zlib

from django.conf import settings
from django.core.cache import cache
from rest_framework_extensions.cache.decorators import CacheResponse
from rest_framework_extensions.key_constructor.bits import KeyBitBase, QueryParamsKeyBit, UserKeyBit
from rest_framework_extensions.key_constructor.constructors import (
    DefaultListKeyConstructor, DefaultObjectKeyConstructor
)

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
    # The UserKeyBit ensures that responses are only cached on a per-user basis,
    # to avoid the issue where another user's username will appear in the api view
    # rendered response, even though you are not actually the other user.
    user = UserKeyBit()


class TimestampedObjectKeyConstructor(DefaultObjectKeyConstructor):
    timestamp = ApiTimestampKeyBit()
    # The DefaultObjectKeyConstructor doesn't include querystring parameters
    # in its cache key.
    querystring = QueryParamsKeyBit()
    # The UserKeyBit ensures that responses are only cached on a per-user basis,
    # to avoid the issue where another user's username will appear in the api view
    # rendered response, even though you are not actually the other user.
    user = UserKeyBit()


def timestamped_list_key_constructor(*args, **kwargs):  # pylint: disable=unused-argument
    return TimestampedListKeyConstructor()(**kwargs)


def timestamped_object_key_constructor(*args, **kwargs):  # pylint: disable=unused-argument
    return TimestampedObjectKeyConstructor()(**kwargs)


def set_api_timestamp(timestamp):
    cache.set(API_TIMESTAMP_KEY, timestamp, None)


def api_change_receiver(sender, **kwargs):  # pylint: disable=unused-argument
    """
    Receiver function for handling post_save and post_delete signals emitted by
    course_metadata models.
    """
    timestamp = time.time()

    logger.debug(
        '{model_name} model changed. Updating API timestamp to {timestamp}.'.format(
            model_name=sender.__name__,
            timestamp=timestamp
        )
    )

    set_api_timestamp(timestamp)


class CompressedCacheResponse(CacheResponse):
    """
    Subclasses CacheResponse to allow for compression of content going into the cache
    See https://github.com/chibisov/drf-extensions/blob/0.3.1/rest_framework_extensions/cache/decorators.py#L52
    for the implementation of process_cache_response without compression
    """
    def process_cache_response(self, view_instance, view_method, request, args, kwargs):
        key = self.calculate_key(
            view_instance=view_instance,
            view_method=view_method,
            request=request,
            args=args,
            kwargs=kwargs
        )
        response = self.cache.get(key)

        if not response:
            response = view_method(view_instance, request, *args, **kwargs)
            response = view_instance.finalize_response(request, response, *args, **kwargs)
            response.render()  # should be rendered, before pickling while storing to cache

            if not response.status_code >= 400 or self.cache_errors:
                self.cache.set(key, response, self.timeout)

        if not hasattr(response, '_closable_objects'):
            response._closable_objects = []  # pylint: disable=protected-access

        try:
            response.data = zlib.decompress(response.data)
        except TypeError:
            # If we get a type error, the response data was never compressed
            pass

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

    @compressed_cache_response(key_func=list_cache_key_func, timeout=list_cache_timeout)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @compressed_cache_response(key_func=object_cache_key_func, timeout=object_cache_timeout)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)
