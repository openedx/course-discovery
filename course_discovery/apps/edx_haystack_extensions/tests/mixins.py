from django.conf import settings
from elasticsearch.helpers import bulk
from haystack.backends import BaseSearchBackend
from mock import patch

from course_discovery.apps.core.tests.mixins import ElasticsearchTestMixin


class SearchBackendTestMixin(ElasticsearchTestMixin):
    backend = None
    backend_class = None

    def setUp(self):
        super(SearchBackendTestMixin, self).setUp()
        self.backend = self.get_backend()

    def get_backend(self, connection_alias='default', **connection_options):
        """ Instantiates a search backend with the specified parameters. """
        connection_options = dict(settings.HAYSTACK_CONNECTIONS.get(connection_alias, {}), **connection_options)
        return self.backend_class(connection_alias, **connection_options)  # pylint: disable=not-callable

    def record_count(self):
        """ Returns a count of all records in the index. """
        return self.backend.conn.count(index=self.backend.index_name)['count']


class SimpleQuerySearchBackendMixinTestMixin(SearchBackendTestMixin):
    """ Test class mixin for testing children of SimpleQuerySearchBackendMixin. """

    all_query_string = '*:*'
    specific_query_string = 'tests:test query'
    simple_query = {
        'query': specific_query_string,
        'analyze_wildcard': True,
        'auto_generate_phrase_queries': True,
    }

    def test_build_search_kwargs_all_qs_with_filter(self):
        with patch.object(BaseSearchBackend, 'build_models_list', return_value=['course_metadata.course']):
            kwargs = self.backend.build_search_kwargs(self.all_query_string)

        self.assertIsNone(kwargs['query'].get('query_string'))
        self.assertIsNone(kwargs['query']['filtered']['query'].get('query_string'))

    def test_build_search_kwargs_specific_qs_with_filter(self):
        with patch.object(BaseSearchBackend, 'build_models_list', return_value=['course_metadata.course']):
            kwargs = self.backend.build_search_kwargs(self.specific_query_string)

        self.assertIsNone(kwargs['query'].get('query_string'))
        self.assertDictEqual(kwargs['query']['filtered']['query'].get('query_string'), self.simple_query)

    def test_build_search_kwargs_all_qs_no_filter(self):
        with patch.object(BaseSearchBackend, 'build_models_list', return_value=[]):
            kwargs = self.backend.build_search_kwargs(self.all_query_string)

        self.assertIsNone(kwargs['query'].get('filtered'))
        self.assertIsNone(kwargs['query'].get('query_string'))

    def test_build_search_kwargs_specific_qs_no_filter(self):
        with patch.object(BaseSearchBackend, 'build_models_list', return_value=[]):
            kwargs = self.backend.build_search_kwargs(self.specific_query_string)

        self.assertIsNone(kwargs['query'].get('filtered'))
        self.assertDictEqual(kwargs['query'].get('query_string'), self.simple_query)


class NonClearingSearchBackendMixinTestMixin(SearchBackendTestMixin):
    """ Test class mixin for testing children of NonClearingSearchBackendMixin. """

    def test_clear(self):
        """ Verify the clear() method does NOT remove any items from the index. """
        # Create a record
        bulk(self.backend.conn, [{'text': 'Testing!'}], index=self.backend.index_name, doc_type='test')
        self.refresh_index()

        original_count = self.record_count()
        self.assertGreater(original_count, 0)

        # This method should not touch any records.
        self.backend.clear()
        self.assertEqual(self.record_count(), original_count)
