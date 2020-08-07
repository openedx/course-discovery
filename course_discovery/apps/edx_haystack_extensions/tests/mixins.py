from unittest.mock import patch

from django.conf import settings
from elasticsearch.helpers import bulk
from haystack import connections as haystack_connections
from haystack.backends import BaseSearchBackend

from course_discovery.apps.core.tests.mixins import ElasticsearchTestMixin
from course_discovery.apps.edx_haystack_extensions.elasticsearch_boost_config import get_elasticsearch_boost_config


class SearchBackendTestMixin(ElasticsearchTestMixin):
    backend = None
    backend_class = None

    def setUp(self):
        super().setUp()
        self.backend = self.get_backend()

    def get_backend(self, connection_alias='default', **connection_options):
        """ Instantiates a search backend with the specified parameters. """
        connection_options = dict(settings.HAYSTACK_CONNECTIONS.get(connection_alias, {}), **connection_options)
        return self.backend_class(connection_alias, **connection_options)  # pylint: disable=not-callable

    def record_count(self):
        """ Returns a count of all records in the index. """
        return self.backend.conn.count(index=self.backend.index_name)['count']


class SearchIndexTestMixin:
    backend = None
    index_prefix = None  # The backend.index_name is manipulated during operation, so we snapshot prefix during setUp

    def setUp(self):
        super().setUp()
        self.backend = haystack_connections['default'].get_backend()
        self.index_prefix = self.backend.index_name

    def tearDown(self):
        """ Remove the indexes we created and reset the backend index_name."""
        self.backend.conn.indices.delete(index=self.index_prefix + '_*')
        self.backend.index_name = self.index_prefix
        super().tearDown()


class SimpleQuerySearchBackendMixinTestMixin(SearchBackendTestMixin):
    """ Test class mixin for testing children of SimpleQuerySearchBackendMixin. """

    all_query_string = '*:*'
    specific_query_string = 'tests:test query'
    simple_query = {
        'query': specific_query_string,
        'analyze_wildcard': True,
        'auto_generate_phrase_queries': True,
    }

    def _default_function_score(self):
        boost_config = get_elasticsearch_boost_config()
        boost_config['function_score']['query'] = {'query_string': self.simple_query}
        return boost_config

    def test_build_search_kwargs_all_qs_with_filter(self):
        with patch.object(BaseSearchBackend, 'build_models_list', return_value=['course_metadata.course']):
            kwargs = self.backend.build_search_kwargs(self.all_query_string)

        self.assertIsNone(kwargs['query'].get('query_string'))
        self.assertIsNone(kwargs['query']['filtered']['query'].get('query_string'))

    def test_build_search_kwargs_specific_qs_with_filter(self):
        with patch.object(BaseSearchBackend, 'build_models_list', return_value=['course_metadata.course']):
            kwargs = self.backend.build_search_kwargs(self.specific_query_string)

        self.assertIsNone(kwargs['query'].get('query_string'))
        self.assertDictEqual(kwargs['query']['filtered'].get('query'), self._default_function_score())

    def test_build_search_kwargs_all_qs_no_filter(self):
        with patch.object(BaseSearchBackend, 'build_models_list', return_value=[]):
            kwargs = self.backend.build_search_kwargs(self.all_query_string)

        self.assertIsNone(kwargs['query'].get('filtered'))
        self.assertIsNone(kwargs['query'].get('query_string'))

    def test_build_search_kwargs_specific_qs_no_filter(self):
        with patch.object(BaseSearchBackend, 'build_models_list', return_value=[]):
            kwargs = self.backend.build_search_kwargs(self.specific_query_string)

        self.assertIsNone(kwargs['query'].get('filtered'))
        self.assertDictEqual(kwargs['query'], self._default_function_score())

    def test_build_search_kwargs_function_score(self):
        test_elasticsearch_boost_config = {
            'function_score': {
                'functions': [
                    {
                        'filter': {
                            'term': {
                                'type': 'micromasters'
                            }
                        },
                        'weight': 10.0
                    }
                ],
                'boost': 5.0,
                'score_mode': 'multiply',
                'boost_mode': 'sum'
            }
        }
        with patch('course_discovery.apps.edx_haystack_extensions.backends.get_elasticsearch_boost_config',
                   return_value=test_elasticsearch_boost_config):
            with patch.object(BaseSearchBackend, 'build_models_list', return_value=[]):
                kwargs = self.backend.build_search_kwargs(self.specific_query_string)

        function_score = test_elasticsearch_boost_config['function_score']

        expected_function_score = {
            'function_score': function_score
        }
        expected_function_score['function_score']['query'] = {
            'query_string': self.simple_query
        }
        self.assertDictEqual(kwargs['query'], expected_function_score)


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
