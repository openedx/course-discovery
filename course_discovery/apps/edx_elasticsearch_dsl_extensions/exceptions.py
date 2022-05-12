from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.exceptions import APIException


class InvalidQuery(APIException):
    """
    API exception.

    Raised when, when executing a request to fetch data from Elasticsearch,
    there were used incorrect parameters.
    In this case, the Elasticsearch instance itself responds with an exception
    `search_phase_execution_exception`.
    """
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = _(
        "Request could not be completed due to an incorrect ElasticSearch query parameters"
    )
    default_code = "invalid_query"
