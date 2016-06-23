from haystack.backends.elasticsearch_backend import ElasticsearchSearchBackend, ElasticsearchSearchEngine


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

        if search_kwargs['query'].get('filtered', {}).get('query', {}).get('query_string'):
            search_kwargs['query']['filtered']['query']['query_string'] = simple_query
        elif search_kwargs['query'].get('query_string'):
            search_kwargs['query']['query_string'] = simple_query

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
class EdxElasticsearchSearchBackend(SimpleQuerySearchBackendMixin, NonClearingSearchBackendMixin,
                                    ElasticsearchSearchBackend):
    pass


class EdxElasticsearchSearchEngine(ElasticsearchSearchEngine):
    backend = EdxElasticsearchSearchBackend
