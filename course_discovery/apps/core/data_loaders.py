""" Data loaders. """
import abc
import logging

from dateutil.parser import parse
from django.utils.functional import cached_property
from edx_rest_api_client.client import EdxRestApiClient
from opaque_keys.edx.keys import CourseKey

logger = logging.getLogger(__name__)


class AbstractDataLoader:
    """ Base class for all data loaders.

    Attributes:
        api_url (str): URL of the API from which data is loaded
        access_token (str): OAuth2 access token
        PAGE_SIZE (int): Number of items to load per API call
    """
    __metaclass__ = abc.ABCMeta
    PAGE_SIZE = 50
    SUPPORTED_TOKEN_TYPES = ('bearer', 'jwt',)

    def __init__(self, api_url, access_token, token_type):
        """
        Arguments:
            api_url (str): URL of the API from which data is loaded
            access_token (str): OAuth2 access token
            token_type (str): The type of access token passed in (e.g. Bearer, JWT)
        """
        token_type = token_type.lower()

        if token_type not in self.SUPPORTED_TOKEN_TYPES:
            raise ValueError('The token type {token_type} is invalid!'.format(token_type=token_type))

        self.access_token = access_token
        self.api_url = api_url
        self.token_type = token_type

    @cached_property
    def api_client(self):
        """
        Returns an authenticated API client ready to call the API from which data is loaded.

        Returns:
            EdxRestApiClient
        """
        kwargs = {}

        if self.token_type == 'jwt':
            kwargs['jwt'] = self.access_token
        else:
            kwargs['oauth_access_token'] = self.access_token

        return EdxRestApiClient(self.api_url, **kwargs)

    @abc.abstractmethod
    def ingest(self):  # pragma: no cover
        """ Load data for all supported objects (e.g. courses, runs). """
        pass

    @classmethod
    def clean_string(cls, s):
        """ Removes all leading and trailing spaces. Returns None if the resulting string is empty. """
        if not isinstance(s, str):
            return s

        return s.strip() or None

    @classmethod
    def clean_strings(cls, data):
        """ Iterates over all string values, removing leading and trailing spaces,
        and replacing empty strings with None. """
        return {k: cls.clean_string(v) for k, v in data.items()}

    @classmethod
    def parse_date(cls, date_string):
        """
        Returns a parsed date.

        Args:
            date_string (str): String to be parsed.

        Returns:
            datetime, or None
        """
        if date_string:
            return parse(date_string)

        return None

    @classmethod
    def convert_course_run_key(cls, course_run_key_str):
        """
        Given a serialized course run key, return the corresponding
        serialized course key.

        Args:
            course_run_key_str (str): The serialized course run key.

        Returns:
            str
        """
        course_run_key = CourseKey.from_string(course_run_key_str)
        return '{org}+{course}'.format(org=course_run_key.org, course=course_run_key.course)
