import logging

import elasticsearch
from haystack.backends import log_query
from haystack.backends.elasticsearch_backend import ElasticsearchSearchBackend, ElasticsearchSearchEngine
from haystack.models import SearchResult

from course_discovery.apps.edx_haystack_extensions.elasticsearch_boost_config import get_elasticsearch_boost_config

logger = logging.getLogger(__name__)


class SimpleQuerySearchBackendMixin(object):
    """
    Mixin for simplifying Elasticsearch queries.

    Uses a basic query string query.
    """

    def build_search_kwargs(self, *args, **kwargs):
        """
        Override default `build_search_kwargs` method to set simpler default search query settings.

        source:
          https://github.com/django-haystack/django-haystack/blob/master/haystack/backends/elasticsearch_backend.py#L254
        Without this override the default is:
          'query_string': {
            'default_field': content_field,
            'default_operator': DEFAULT_OPERATOR,
            'query': query_string,
            'analyze_wildcard': True,
            'auto_generate_phrase_queries': True,
            'fuzzy_min_sim': FUZZY_MIN_SIM,
            'fuzzy_max_expansions': FUZZY_MAX_EXPANSIONS,
          }
        """
        query_string = args[0]
        search_kwargs = super(SimpleQuerySearchBackendMixin, self).build_search_kwargs(*args, **kwargs)

        simple_query = {
            'query': query_string,
            'analyze_wildcard': True,
            'auto_generate_phrase_queries': True,
        }

        # https://www.elastic.co/guide/en/elasticsearch/reference/1.5/query-dsl-function-score-query.html
        function_score_config = get_elasticsearch_boost_config()['function_score']
        function_score_config['query'] = {
            'query_string': simple_query
        }

        function_score = {
            'function_score': function_score_config
        }

        if search_kwargs['query'].get('filtered', {}).get('query'):
            search_kwargs['query']['filtered']['query'] = function_score
        elif search_kwargs['query'].get('query_string'):
            search_kwargs['query'] = function_score

        return search_kwargs


class NonClearingSearchBackendMixin(object):
    """
    Mixin that prevents indexes from being cleared.

    Inherit this class if you would prefer, for example, to create a new index when you rebuild indexes rather than
    clearing/updating indexes in place as Haystack normally does.
    """

    def clear(self, models=None, commit=True):  # pylint: disable=unused-argument
        """ Does NOT clear the index.

        Instead of clearing the index, this method logs the fact that the inheriting class does NOT clear
        indexes, advising the user to use the appropriate tools to manually clear the index.
        """
        self.log.info('%s does NOT clear indexes. Indexes should be manually cleared using the APIs/tools appropriate '
                      'for this search service.', self.__class__.__name__)


# pylint: disable=abstract-method
class ConfigurableElasticBackend(ElasticsearchSearchBackend):
    def specify_analyzers(self, mapping, field, index_analyzer, search_analyzer):
        """ Specify separate index and search analyzers for the given field.
          Args:
            mapping (dict): /_mapping attribute on index (maps analyzers to fields)
            field (str): which field to modify
            index_analyzer (str): name of the index_analyzer (should be defined in the /_settings attribute)
            search_analyzer (str): name of the search_analyzer (should be defined in the /_settings attribute)
        """
        # The generic analyzer is used for both if index_analyzer and search_analyzer are not specified
        mapping[field].pop('analyzer')
        mapping[field].update({
            'index_analyzer': index_analyzer,
            'search_analyzer': search_analyzer
        })

    def build_schema(self, fields):
        content_field_name, mapping = super().build_schema(fields)

        # The aggregation_key is intended to be used for computing distinct record counts. We do not want it to be
        # analyzed because doing so would result in more values being counted, as each key would be broken down
        # into substrings by the analyzer.
        if mapping.get('aggregation_key'):
            mapping['aggregation_key']['index'] = 'not_analyzed'
            del mapping['aggregation_key']['analyzer']

        # Fields default to snowball analyzer, this keeps snowball functionality, but adds synonym functionality
        snowball_with_synonyms = 'snowball_with_synonyms'
        for field, value in mapping.items():
            if value.get('analyzer') == 'snowball':
                self.specify_analyzers(mapping=mapping, field=field,
                                       index_analyzer=snowball_with_synonyms,
                                       search_analyzer=snowball_with_synonyms)
        # Use the ngram analyzer as the index_analyzer and the lowercase analyzer as the search_analyzer
        # This is necessary to support partial searches/typeahead
        # If we used ngram analyzer for both, then 'running' would get split into ngrams like "ing"
        # and all words containing ing would come back in typeahead.
        self.specify_analyzers(mapping=mapping, field='title_autocomplete',
                               index_analyzer='ngram_analyzer', search_analyzer=snowball_with_synonyms)
        self.specify_analyzers(mapping=mapping, field='authoring_organizations_autocomplete',
                               index_analyzer='ngram_analyzer', search_analyzer=snowball_with_synonyms)

        return (content_field_name, mapping)


# pylint: disable=abstract-method
class EdxElasticsearchSearchBackend(SimpleQuerySearchBackendMixin, NonClearingSearchBackendMixin,
                                    ConfigurableElasticBackend):
    @log_query
    def search(self, query_string, **kwargs):
        if len(query_string) == 0:
            return {
                'results': [],
                'hits': 0,
            }

        # NOTE (CCB): Haystack by default attempts to read/update the index mapping. Given that our mapping doesn't
        # frequently change, this is a waste of three API calls. Stop it! We set our mapping when we create the index.
        self.setup_complete = True
        # if not self.setup_complete:
        #     self.setup()
        logger.info('DEBUG: Skipped Haystack setup call')

        search_kwargs = self.build_search_kwargs(query_string, **kwargs)
        search_kwargs['from'] = kwargs.get('start_offset', 0)

        order_fields = set()
        for order in search_kwargs.get('sort', []):
            for key in order.keys():
                order_fields.add(key)

        geo_sort = '_geo_distance' in order_fields

        end_offset = kwargs.get('end_offset')
        start_offset = kwargs.get('start_offset', 0)
        if end_offset is not None and end_offset > start_offset:
            search_kwargs['size'] = end_offset - start_offset

        try:
            # pylint: disable=unexpected-keyword-arg
            raw_results = self.conn.search(body=search_kwargs,
                                           index=self.index_name,
                                           doc_type='modelresult',
                                           _source=True)
        except elasticsearch.TransportError as e:
            if not self.silently_fail:
                raise

            self.log.error("Failed to query Elasticsearch using '%s': %s", query_string, e, exc_info=True)
            raw_results = {}

        return self._process_results(raw_results,
                                     highlight=kwargs.get('highlight'),
                                     result_class=kwargs.get('result_class', SearchResult),
                                     distance_point=kwargs.get('distance_point'),
                                     geo_sort=geo_sort)


class EdxElasticsearchSearchEngine(ElasticsearchSearchEngine):
    backend = EdxElasticsearchSearchBackend
