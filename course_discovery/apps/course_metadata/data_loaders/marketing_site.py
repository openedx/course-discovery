import abc
import concurrent.futures
import csv
import logging
import re
from urllib.parse import parse_qs, urlencode, urlparse
from uuid import UUID

from django.contrib.staticfiles import finders
from django.db import IntegrityError
from django.utils.functional import cached_property
from opaque_keys.edx.keys import CourseKey

from course_discovery.apps.course_metadata.data_loaders import AbstractDataLoader
from course_discovery.apps.course_metadata.models import Course, Organization, Subject
from course_discovery.apps.course_metadata.utils import MarketingSiteAPIClient, clean_html

logger = logging.getLogger(__name__)

DRUPAL_REDIRECT_CSV_FILE = 'data/redirects.csv'


class AbstractMarketingSiteDataLoader(AbstractDataLoader):
    def __init__(self, partner, api_url, access_token=None, token_type=None, max_workers=None,
                 is_threadsafe=False, **kwargs):
        super(AbstractMarketingSiteDataLoader, self).__init__(
            partner, api_url, access_token, token_type, max_workers, is_threadsafe, **kwargs
        )

        if not (self.partner.marketing_site_api_username and self.partner.marketing_site_api_password):
            msg = 'Marketing Site API credentials are not properly configured for Partner [{partner}]!'.format(
                partner=partner.short_code)
            raise Exception(msg)

    @cached_property
    def api_client(self):

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

        return self.api_client.get(url)

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


class SubjectMarketingSiteDataLoader(AbstractMarketingSiteDataLoader):
    @property
    def node_type(self):
        return 'subject'

    def process_node(self, data):
        slug = data['field_subject_url_slug']
        if ('language' not in data) or (data['language'] == 'und'):
            language_code = 'en'
        else:
            language_code = data['language']
        defaults = {
            'uuid': data['uuid'],
            'name': data['title'],
            'description': clean_html(data['body']['value']),
            'subtitle': clean_html(data['field_subject_subtitle']['value']),
            'card_image_url': self._get_nested_url(data.get('field_subject_card_image')),
            # NOTE (CCB): This is not a typo. Yes, the banner image for subjects is in a field with xseries in the name.
            'banner_image_url': self._get_nested_url(data.get('field_xseries_banner_image'))
        }

        # There is a bug with django-parler when using django's update_or_create() so we manually update or create.
        try:
            subject = Subject.objects.get(slug=slug, partner=self.partner)
            subject.set_current_language(language_code)
            for key, value in defaults.items():
                setattr(subject, key, value)
            subject.save()
        except Subject.DoesNotExist:
            new_values = {'slug': slug, 'partner': self.partner, '_current_language': language_code}
            new_values.update(defaults)
            subject = Subject(**new_values)
            subject.save()

        logger.info('Processed subject with slug [%s].', slug)
        return subject


class SchoolMarketingSiteDataLoader(AbstractMarketingSiteDataLoader):
    @property
    def node_type(self):
        return 'school'

    def process_node(self, data):
        # NOTE: Some titles in Drupal have the form "UC BerkeleyX" however, course keys (for which we use the
        # organization key) cannot contain spaces.
        key = data['title'].replace(' ', '')
        uuid = UUID(data['uuid'])

        defaults = {
            'name': data['field_school_name'],
            'description': clean_html(data['field_school_description']['value']),
            'logo_image_url': self._get_nested_url(data.get('field_school_image_logo')),
            'banner_image_url': self._get_nested_url(data.get('field_school_image_banner')),
            'partner': self.partner,
        }

        try:
            school = Organization.objects.get(uuid=uuid, partner=self.partner)
            Organization.objects.filter(pk=school.pk).update(**defaults)
            logger.info('Updated school with key [%s].', school.key)
        except Organization.DoesNotExist:
            # NOTE: Some organizations' keys do not match the title. For example, "UC BerkeleyX" courses use
            # BerkeleyX as the key. Those fixes will be made manually after initial import, and we don't want to
            # override them with subsequent imports. Thus, we only set the key when creating a new organization.
            defaults['key'] = key
            defaults['uuid'] = uuid
            school = Organization.objects.create(**defaults)
            logger.info('Created school with key [%s].', school.key)

        self.set_tags(school, data)

        logger.info('Processed school with key [%s].', school.key)
        return school

    def set_tags(self, school, data):
        tags = []
        mapping = {
            'field_school_is_founder': 'founder',
            'field_school_is_charter': 'charter',
            'field_school_is_contributor': 'contributor',
            'field_school_is_partner': 'partner',
            'field_school_is_display': 'displayed_on_schools_and_partners_page',
        }

        for field, tag in mapping.items():
            if data.get(field, False):
                tags.append(tag)

        school.tags.set(*tags, clear=True)


class SponsorMarketingSiteDataLoader(AbstractMarketingSiteDataLoader):
    @property
    def node_type(self):
        return 'sponsorer'

    def process_node(self, data):
        uuid = data['uuid']
        body = (data['body'] or {}).get('value')

        if body:
            body = clean_html(body)

        defaults = {
            'key': data['url'].split('/')[-1],
            'name': data['title'],
            'description': body,
            'logo_image_url': data['field_sponsorer_image']['url'],
        }
        sponsor, __ = Organization.objects.update_or_create(uuid=uuid, partner=self.partner, defaults=defaults)

        logger.info('Processed sponsor with UUID [%s].', uuid)
        return sponsor


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
            course = Course.objects.get(key__iexact=course_key)
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
