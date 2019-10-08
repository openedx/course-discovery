import abc
import concurrent.futures
import logging
from urllib.parse import parse_qs, urlencode, urlparse

from django.utils.functional import cached_property

from course_discovery.apps.course_metadata.data_loaders import AbstractDataLoader
from course_discovery.apps.course_metadata.models import Subject
from course_discovery.apps.course_metadata.utils import MarketingSiteAPIClient

logger = logging.getLogger(__name__)


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

    @abc.abstractproperty
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
            'description': self.clean_html(data['body']['value']),
            'subtitle': self.clean_html(data['field_subject_subtitle']['value']),
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
