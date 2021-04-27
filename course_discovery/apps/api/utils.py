import hashlib
import logging
from traceback import format_exc as _format_exc

from django.conf import settings as _settings
from rest_framework.response import Response as _Response
from rest_framework.status import HTTP_500_INTERNAL_SERVER_ERROR
from rest_framework.views import exception_handler as _drf_exception_handler
import six


logger = logging.getLogger(__name__)


def cast2int(value, name):
    """
    Attempt to cast the provided value to an integer.

    Arguments:
        value (str): A value to cast to an integer.
        name (str): A name to log if casting fails.

    Raises:
        ValueError, if the provided value can't be converted. A helpful
            error message is logged first.

    Returns:
        int | None
    """
    if value is None:
        return value

    try:
        return int(value)
    except ValueError:
        logger.exception('The "%s" parameter requires an integer value. "%s" is invalid.', name, value)
        raise


def get_query_param(request, name):
    """
    Get a query parameter and cast it to an integer.
    """
    # This facilitates DRF's schema generation. For more, see
    # https://github.com/encode/django-rest-framework/blob/3.6.3/rest_framework/schemas.py#L383
    if request is None:
        return

    return cast2int(request.query_params.get(name), name)


def get_cache_key(**kwargs):
    """
    Get MD5 encoded cache key for given arguments.

    Here is the format of key before MD5 encryption.
        key1:value1__key2:value2 ...

    Example:
        >>> get_cache_key(site_domain="example.com", resource="catalogs")
        # Here is key format for above call
        # "site_domain:example.com__resource:catalogs"
        a54349175618ff1659dee0978e3149ca

    Arguments:
        **kwargs: Key word arguments that need to be present in cache key.

    Returns:
         An MD5 encoded key uniquely identified by the key word arguments.
    """
    key = '__'.join(['{}:{}'.format(item, value) for item, value in six.iteritems(kwargs)])

    return hashlib.md5(key.encode('utf-8')).hexdigest()


def learning_tribes_exception_handler(exc, context):
    response = _drf_exception_handler(exc, context)
    if response:
        return response

    desc = 'view[{}] , method [{}] , error: {}'.format(
        context['view'], context['request'].method, exc
    ) \
        if not _settings.DEBUG else _format_exc()

    return _Response(
        {'api_error_message': desc},
        status=HTTP_500_INTERNAL_SERVER_ERROR
    )
