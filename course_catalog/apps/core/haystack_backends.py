from haystack.backends.elasticsearch_backend import ElasticsearchSearchBackend, ElasticsearchSearchEngine


# pylint: disable=abstract-method
class SimplifiedElasticsearchSearchBackend(ElasticsearchSearchBackend):
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
        search_kwargs = super(SimplifiedElasticsearchSearchBackend, self).build_search_kwargs(*args, **kwargs)

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


class SimplifiedElasticsearchSearchEngine(ElasticsearchSearchEngine):
    backend = SimplifiedElasticsearchSearchBackend
