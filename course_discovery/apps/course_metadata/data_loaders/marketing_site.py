import abc
import concurrent.futures
import csv
import logging
import re
from urllib.parse import parse_qs, urlencode, urlparse

from django.contrib.staticfiles import finders
from django.db import IntegrityError
from opaque_keys.edx.keys import CourseKey

from course_discovery.apps.course_metadata.data_loaders import AbstractDataLoader
from course_discovery.apps.course_metadata.models import Course
from course_discovery.apps.course_metadata.utils import MarketingSiteAPIClient

logger = logging.getLogger(__name__)

DRUPAL_REDIRECT_CSV_FILE = 'data/redirects.csv'


class AbstractMarketingSiteDataLoader(AbstractDataLoader):
    def __init__(self, partner, api_url, max_workers=None, is_threadsafe=False):
        super(AbstractMarketingSiteDataLoader, self).__init__(partner, api_url, max_workers, is_threadsafe)

        if not (self.partner.marketing_site_api_username and self.partner.marketing_site_api_password):
            msg = 'Marketing Site API credentials are not properly configured for Partner [{partner}]!'.format(
                partner=partner.short_code)
            raise Exception(msg)

    def marketing_api_client(self):
        marketing_site_api_client = MarketingSiteAPIClient(
            self.partner.marketing_site_api_username,
            self.partner.marketing_site_api_password,
            self.api_url
        )

        return marketing_site_api_client.api_session

    def get_query_kwargs(self):
        return {
            'type': self.node_type,
            'max-depth': 2,
            'load-entity-refs': 'file',
        }

    def ingest(self):
        """ Load data for all supported objects (e.g. courses, runs). """
        initial_page = 0
        response = self._request(initial_page)
        self._process_response(response)

        data = response.json()
        if 'next' in data:
            # Add one to avoid requesting the first page again and to make sure
            # we get the last page when range() is used below.
            pages = [self._extract_page(url) + 1 for url in (data['first'], data['last'])]
            pagerange = range(*pages)

            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                if self.is_threadsafe:  # pragma: no cover
                    for page in pagerange:
                        executor.submit(self._load_data, page)
                else:
                    for future in [executor.submit(self._request, page) for page in pagerange]:
                        response = future.result()
                        self._process_response(response)

    def _load_data(self, page):  # pragma: no cover
        """Make a request for the given page and process the response."""
        response = self._request(page)
        self._process_response(response)

    def _request(self, page):
        """Make a request to the marketing site."""
        kwargs = {'page': page}
        kwargs.update(self.get_query_kwargs())

        qs = urlencode(kwargs)
        url = '{root}/node.json?{qs}'.format(root=self.api_url, qs=qs)

        return self.marketing_api_client().get(url)

    def _check_status_code(self, response):
        """Check the status code on a response from the marketing site."""
        status_code = response.status_code
        if status_code != 200:
            msg = 'Failed to retrieve data from {url}\nStatus Code: {status}\nBody: {body}'.format(
                url=response.url, status=status_code, body=response.content)
            logger.error(msg)
            raise Exception(msg)

    def _extract_page(self, url):
        """Extract page number from a marketing site URL."""
        qs = parse_qs(urlparse(url).query)

        return int(qs['page'][0])

    def _process_response(self, response):
        """Process a response from the marketing site."""
        self._check_status_code(response)

        data = response.json()
        for node in data['list']:
            try:
                url = node['url']
                node = self.clean_strings(node)
                self.process_node(node)
            except Exception:  # pylint: disable=broad-except
                logger.exception('Failed to load %s.', url)

    def _get_nested_url(self, field):
        """ Helper method that retrieves the nested `url` field in the specified field, if it exists.
        This works around the fact that Drupal represents empty objects as arrays instead of objects."""
        field = field or {}
        return field.get('url')

    @abc.abstractmethod
    def process_node(self, data):  # pragma: no cover
        pass

    @property
    @abc.abstractmethod
    def node_type(self):  # pragma: no cover
        pass


class CourseMarketingSiteDataLoader(AbstractMarketingSiteDataLoader):
    """
    This is only used to handle redirect data on a course-by-course basis.
    We are not currently pulling in course data from the marketing site.
    """
    redirects = {}
    standard_course_url_regex = re.compile('^/?course/([^/]*)$')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.load_redirect_data()

    def load_redirect_data(self):
        redirects_file = finders.find(DRUPAL_REDIRECT_CSV_FILE)
        with open(redirects_file) as redirect_csv:
            reader = csv.DictReader(redirect_csv, fieldnames=('redirect_url', 'node', 'redirect_type'))
            # Order data so that we can pull it out via node ids
            for row in reader:
                # Node id in CSV is stored as 'node/1234'.
                # Ignore anything that doesn't match.
                split_string = row['node'].split('/')
                if len(split_string) > 1:
                    node_id = split_string[1]
                    if node_id in self.redirects.keys():
                        self.redirects[node_id].append(row)
                    else:
                        self.redirects[node_id] = [row]

    @property
    def node_type(self):
        return 'course'

    def find_course_key(self, data):
        # Parse key up front to ensure it's a valid key.
        # If the course is so messed up that we can't even parse the key, we don't want it.
        course_run_key = CourseKey.from_string(data['field_course_id'])
        return self.get_course_key_from_course_run_key(course_run_key)

    def process_node(self, data):
        node_id = data.get('nid')
        logger.info('Processing course at node %s', node_id)

        node_redirects = self.redirects.get(node_id, [])
        course_key = self.find_course_key(data)
        try:
            course = Course.objects.get(key__iexact=course_key, partner=self.partner)
        except Course.DoesNotExist:
            logger.info('No course found for %s', course_key)
            return

        # first add a redirect from the node URL itself
        try:
            obj, created = course.url_redirects.get_or_create(course=course, value='node/{}'.format(node_id),
                                                              partner=course.partner)
            if created:
                course.url_redirects.add(obj)
        except IntegrityError:
            logger.warning('Integrity error attempting to add redirect node/%s to course %s', node_id, course_key)

        for redirect_row in node_redirects:
            redirect = redirect_row['redirect_url']
            matched = self.standard_course_url_regex.match(redirect)
            if matched:
                # if redirect path is /course/something, just add 'something' to url_slug_history
                try:
                    obj, created = course.url_slug_history.get_or_create(course=course, url_slug=matched.group(1),
                                                                         defaults={
                                                                         'is_active': False,
                                                                         'is_active_on_draft': False,
                                                                         'partner': course.partner
                                                                         })
                    if created:
                        course.url_slug_history.add(obj)
                except IntegrityError:
                    logger.warning('Integrity error attempting to add url slug {slug} to course {course}'.format(
                        slug=matched.group(1), course=course_key
                    ))
                continue
            # redirect path is not /course/something, so add the full path to url_redirects
            try:
                # remove preceding '/' if present for standardization
                redirect = redirect.lstrip('/')
                obj, created = course.url_redirects.get_or_create(
                    course=course,
                    value=redirect,
                    partner=course.partner
                )
                if created:
                    course.url_redirects.add(obj)
            except IntegrityError:
                logger.warning('Integrity error attempting to add path %s to course %s', redirect, course.key)
                continue
