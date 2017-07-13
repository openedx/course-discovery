import logging

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
