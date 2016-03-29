""" Data loaders. """
import abc
import logging

from dateutil.parser import parse
from edx_rest_api_client.client import EdxRestApiClient
from opaque_keys.edx.keys import CourseKey

from course_discovery.apps.course_metadata.models import (
    Organization, Image, Course, CourseRun, CourseOrganization, Video
)

logger = logging.getLogger(__name__)


class AbstractDataLoader(metaclass=abc.ABCMeta):
    """ Base class for all data loaders.

    Attributes:
        api_url (str): URL of the API from which data is loaded
        access_token (str): OAuth2 access token
        PAGE_SIZE (int): Number of items to load per API call
    """

    PAGE_SIZE = 50

    def __init__(self, api_url, access_token):
        """
        Arguments:
            api_url (str): URL of the API from which data is loaded
            access_token (str): OAuth2 access token
        """
        self.access_token = access_token
        self.api_url = api_url

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


class OrganizationsApiDataLoader(AbstractDataLoader):
    """ Loads organizations from the Organizations API. """

    def ingest(self):
        client = EdxRestApiClient(self.api_url, oauth_access_token=self.access_token)
        count = None
        page = 1

        logger.info('Refreshing Organizations from %s....', self.api_url)

        while page:
            response = client.organizations().get(page=page, page_size=self.PAGE_SIZE)
            count = response['count']
            results = response['results']
            logger.info('Retrieved %d organizations...', len(results))

            if response['next']:
                page += 1
            else:
                page = None

            for body in results:
                body = self.clean_strings(body)
                self.update_organization(body)

        logger.info('Retrieved %d organizations from %s.', count, self.api_url)

    def update_organization(self, body):
        image = None
        image_url = body['logo']
        if image_url:
            image_url = image_url.lower()
            image, __ = Image.objects.get_or_create(src=image_url)
        defaults = {
            'name': body['name'],
            'description': body['description'],
            'logo_image': image,
        }
        Organization.objects.update_or_create(key=body['short_name'], defaults=defaults)


class CoursesApiDataLoader(AbstractDataLoader):
    """ Loads course runs from the Courses API. """

    def ingest(self):
        client = EdxRestApiClient(self.api_url, oauth_access_token=self.access_token)
        count = None
        page = 1

        logger.info('Refreshing Courses and CourseRuns from %s....', self.api_url)

        while page:
            response = client.courses().get(page=page, page_size=self.PAGE_SIZE)
            count = response['pagination']['count']
            results = response['results']
            logger.info('Retrieved %d course runs...', len(results))

            if response['pagination']['next']:
                page += 1
            else:
                page = None

            for body in results:
                body = self.clean_strings(body)
                course = self.update_course(body)
                self.update_course_run(course, body)

        logger.info('Retrieved %d course runs from %s.', count, self.api_url)

    def update_course(self, body):
        # NOTE (CCB): Use the data from the CourseKey since the Course API exposes display names for org and number,
        # which may not be unique for an organization.
        course_run_key = CourseKey.from_string(body['id'])
        organization, __ = Organization.objects.get_or_create(key=course_run_key.org)
        course_key = '{org}+{course}'.format(org=organization.key, course=course_run_key.course)
        defaults = {
            'title': body['name']
        }
        course, __ = Course.objects.update_or_create(key=course_key, defaults=defaults)

        course.organizations.clear()
        CourseOrganization.objects.create(
            course=course, organization=organization, relation_type=CourseOrganization.OWNER)

        return course

    def update_course_run(self, course, body):
        defaults = {
            'course': course,
            'start': self.parse_date(body['start']),
            'end': self.parse_date(body['end']),
            'enrollment_start': self.parse_date(body['enrollment_start']),
            'enrollment_end': self.parse_date(body['enrollment_end']),
            'title': body['name'],
            'short_description': body['short_description'],
            'video': self.get_courserun_video(body),
            'pacing_type': self.get_pacing_type(body),
            'image': self.get_courserun_image(body),
        }
        CourseRun.objects.update_or_create(key=body['id'], defaults=defaults)

    def get_pacing_type(self, body):
        pacing = body.get('pacing')

        if pacing:
            pacing = pacing.lower()

        if pacing == 'instructor':
            return CourseRun.INSTRUCTOR_PACED
        elif pacing == 'self':
            return CourseRun.SELF_PACED
        else:
            return None

    def get_courserun_image(self, body):
        image = None
        image_url = body['media'].get('image', {}).get('raw')

        if image_url:
            image_url = image_url.lower()
            image, __ = Image.objects.get_or_create(src=image_url)

        return image

    def get_courserun_video(self, body):
        video = None
        video_url = body['media'].get('course_video', {}).get('uri')

        if video_url:
            video_url = video_url.lower()
            video, __ = Video.objects.get_or_create(src=video_url)

        return video
