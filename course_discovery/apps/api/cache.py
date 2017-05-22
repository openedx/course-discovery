import logging
import time

from django.core.cache import cache
from rest_framework_extensions.key_constructor.bits import KeyBitBase, QueryParamsKeyBit
from rest_framework_extensions.key_constructor.constructors import (
    DefaultListKeyConstructor, DefaultObjectKeyConstructor
)

logger = logging.getLogger(__name__)
API_TIMESTAMP_KEY = 'api_timestamp'


class ApiTimestampKeyBit(KeyBitBase):
    def get_data(self, **kwargs):
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


def set_api_timestamp(timestamp):
    cache.set(API_TIMESTAMP_KEY, timestamp, None)


def api_change_receiver(sender, **kwargs):  # pylint: disable=unused-argument
    """
    Receiver function for handling post_save and post_delete signals emitted by
    course_metadata models.
    """
    timestamp = time.time()

    logger.info(
        '{model_name} model changed. Updating API timestamp to {timestamp}.'.format(
            model_name=sender.__name__,
            timestamp=timestamp
        )
    )

    set_api_timestamp(timestamp)
