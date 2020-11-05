import abc

from dateutil.parser import parse
from edx_rest_framework_extensions.auth.jwt.decoder import configured_jwt_decode_handler

from course_discovery.apps.course_metadata.models import Image, Video


class AbstractDataLoader(metaclass=abc.ABCMeta):
    """ Base class for all data loaders.

    Attributes:
        api_url (str): URL of the API from which data is loaded
        partner (Partner): Partner which owns the data for this data loader
        PAGE_SIZE (int): Number of items to load per API call
    """

    LOADER_MAX_RETRY = 3
    PAGE_SIZE = 50

    def __init__(self, partner, api_url, max_workers=None, is_threadsafe=False):
        """
        Arguments:
            partner (Partner): Partner which owns the APIs and data being loaded
            api_url (str): URL of the API from which data is loaded
            max_workers (int): Number of worker threads to use when traversing paginated responses.
            is_threadsafe (bool): True if multiple threads can be used to write data.
        """
        self.partner = partner
        self.api_url = api_url.strip('/')
        self.api_client = self.partner.lms_api_client
        self.username = self.get_username_from_client(self.api_client)

        self.max_workers = max_workers
        self.is_threadsafe = is_threadsafe

    @abc.abstractmethod
    def ingest(self):  # pragma: no cover
        """ Load data for all supported objects (e.g. courses, runs). """

    def get_username_from_client(self, client):
        token = client.get_jwt_access_token()
        decoded_jwt = configured_jwt_decode_handler(token)
        return decoded_jwt.get('preferred_username')

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
    def get_course_key_from_course_run_key(cls, course_run_key):
        """
        Given a serialized course run key, return the corresponding
        serialized course key.

        Args:
            course_run_key (CourseKey): Course run key.

        Returns:
            str
        """
        return f'{course_run_key.org}+{course_run_key.course}'

    @classmethod
    def _get_or_create_media(cls, media_type, url):
        media = None

        if url:
            media, __ = media_type.objects.get_or_create(src=url)

        return media

    @classmethod
    def get_or_create_video(cls, url, image_url=None):
        video = cls._get_or_create_media(Video, url)

        if video:
            image = cls.get_or_create_image(image_url)
            video.image = image
            video.save()

        return video

    @classmethod
    def get_or_create_image(cls, url):
        return cls._get_or_create_media(Image, url)
