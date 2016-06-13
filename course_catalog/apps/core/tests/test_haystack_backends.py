""" Haystack backend tests. """
from mock import patch

from django.test import TestCase
from haystack.backends import BaseSearchBackend

from course_catalog.apps.core.haystack_backends import SimplifiedElasticsearchSearchBackend


class SimplifiedElasticsearchSearchEngineTests(TestCase):
    """ Tests for core.context_processors.core """
    def setUp(self):
        super(SimplifiedElasticsearchSearchEngineTests, self).setUp()
        self.all_query_string = "*:*"
        self.specific_query_string = "tests:test query"
        self.simple_query = {
            'query': self.specific_query_string,
            'analyze_wildcard': True,
            'auto_generate_phrase_queries': True,
        }
        self.backend = SimplifiedElasticsearchSearchBackend(
            'default',
            URL='http://test-es.example.com',
            INDEX_NAME='testing'
        )

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
