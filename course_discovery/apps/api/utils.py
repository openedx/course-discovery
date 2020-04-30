import hashlib
import logging

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


def get_queryset_filtered_on_organization(queryset, edx_org_filter, edx_org_short_name):
    """
    Get queryset filtered on edx organization short name.

    Arguments:
        queryset (DRF queryset object): DRF Queryset object.
        edx_org_filter (str): Filter to use in queryset.
        edx_org_short_name (str): Edx organization short name.

    Returns:
        A DRF queryset object with organization filter applied.
    """
    return queryset if not edx_org_short_name else queryset.filter(**{edx_org_filter: edx_org_short_name})
