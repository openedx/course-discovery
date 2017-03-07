import elasticsearch

from haystack.backends.elasticsearch_backend import ElasticsearchSearchQuery
from haystack.models import SearchResult


class DistinctCountsSearchQuery(ElasticsearchSearchQuery):
    """ Custom Haystack Query class that computes and caches distinct hit and facet counts for a query."""

    def __init__(self, **kwargs):
        """ Create and return a new instance of DistinctCountsSearchQuery."""
        super(DistinctCountsSearchQuery, self).__init__(**kwargs)
        self._aggregation_key = None
        self._distinct_hit_count = None

    def _clone(self, **kwargs):
        """ Create and return a new DistinctCountsSearchQuery with fields set to match those on the original object."""
        clone = super(DistinctCountsSearchQuery, self)._clone(**kwargs)
        clone._aggregation_key = self._aggregation_key
        clone._distinct_hit_count = self._distinct_hit_count
        return clone

    def set_aggregation_key(self, aggregation_key):
        """
        Set the aggregation_key for this Query. The aggregation_key is the field that should
        be used to group records when computing distinct counts.
        """
        self._aggregation_key = aggregation_key

    def get_distinct_count(self):
        """
        Return the distinct hit count for this query. Calling this method will cause the query to execute if
        it hasn't already been run.
        """
        if self._distinct_hit_count is None:
            # Calling get_count will cause the query to run and both count and distinct_count to be populated.
            self.get_count()
        return self._distinct_hit_count

    def run(self, spelling_query=None, **kwargs):
        """
        Run the query and cache the results.

        Overrides and re-implements ElasticsearchSearchQuery.run so that the custom DistinctCountsSearchBackend
        may be used to execute the query and so that the distinct hit counts may be cached.
        """
        # Make sure that the Query is valid before running it.
        self.validate()

        final_query = self.build_query()
        search_kwargs = self.build_params(spelling_query=spelling_query)

        if kwargs:
            search_kwargs.update(kwargs)

        # Use the DistinctCountsElasticsearchBackendWrapper to execute the query so that distinct hit and query
        # counts may be computed.
        backend = DistinctCountsElasticsearchBackendWrapper(self.backend, self._aggregation_key)
        results = backend.search(final_query, **search_kwargs)

        self._results = results.get('results', [])
        self._hit_count = results.get('hits', 0)
        self._distinct_hit_count = results.get('distinct_hits', 0)
        self._facet_counts = self.post_process_facets(results)
        self._spelling_suggestion = results.get('spelling_suggestion', None)

    def validate(self):
        """ Verify that all Query options are valid and supported by this custom Query class."""
        if self._more_like_this:
            raise RuntimeError('DistinctCountsSearchQuery does not support more_like_this queries.')

        if self._raw_query:
            raise RuntimeError('DistinctCountsSearchQuery does not support raw queries.')

        if self.date_facets:
            raise RuntimeError('DistinctCountsSearchQuery does not support date facets.')

        if self.facets:
            for field, options in self.facets.items():
                self._validate_field_facet_options(field, options)

        if self._aggregation_key is None:
            raise RuntimeError('aggregation_key is required.')

    def _validate_field_facet_options(self, field, options):
        """ Verify that the provided field facet options are valid and can be converted to an aggregation. """
        supported_options = DistinctCountsElasticsearchBackendWrapper.SUPPORTED_FIELD_FACET_OPTIONS
        for option, value in options.items():
            if option not in supported_options:
                msg = 'DistinctCountsSearchQuery only supports a limited set of field facet options.'
                msg += 'Field: {}, Supported Options: ({}), '.format(field, ','.join(supported_options))
                msg += 'Provided Options: ({})'.format(','.join(options.keys()))
                raise RuntimeError(msg)

    def more_like_this(self, *args, **kwargs):
        """ Raise an exception since we do not currently want/need to support more_like_this queries."""
        raise RuntimeError('DistinctCountsSearchQuery does not support more_like_this queries.')

    def run_mlt(self, *args, **kwargs):
        """ Raise an exception since we do not currently want/need to support more_like_this queries."""
        raise RuntimeError('DistinctCountsSearchQuery does not support more_like_this queries.')

    def raw_search(self, *args, **kwargs):
        """ Raise an exception since we do not currently want/need to support raw queries."""
        raise RuntimeError('DistinctCountsSearchQuery does not support raw queries.')

    def run_raw(self, *args, **kwargs):
        """ Raise an exception since we do not currently want/need to support raw queries."""
        raise RuntimeError('DistinctCountsSearchQuery does not support raw queries.')

    def add_date_facet(self, *args, **kwargs):
        """ Raise an exception since we do not currently want/need to support date facets."""
        raise RuntimeError('DistinctCountsSearchQuery does not support date facets.')

    def add_field_facet(self, field, **options):
        """ Add a field facet to the Query. Raise an error if any unsupported options are provided."""
        self._validate_field_facet_options(field, options)
        return super(DistinctCountsSearchQuery, self).add_field_facet(field, **options)


class DistinctCountsElasticsearchBackendWrapper(object):
    """
    Custom backend-like class that enables the computation of distinct hit and facet counts during search queries.

    This class is not meant to be a true ElasticsearchSearchBackend. It is meant to wrap an existing
    ElasticsearchSearchBackend instance and expose a very limited subset of backend functionality.
    """

    # The maximum setting for the elasticsearch cardinality aggregation precision_threshold field.
    # See https://www.elastic.co/guide/en/elasticsearch/reference/1.5/search-aggregations-metrics-cardinality-aggregation.html
    MAX_CARDINALITY_PRECISION = 40000

    # Field facet options that are currently supported for conversion to aggregations.
    SUPPORTED_FIELD_FACET_OPTIONS = {'size'}

    def __init__(self, backend, aggregation_key):
        """
        Initialize a new instance of the DistinctCountsElasticsearchBackendWrapper.

        -- Parameters --
        backend - An ElasticsearchSearchBackend instance.
        aggregation_key - The field that should be used to group records when computing distinct counts.
            It should be a field that is NOT analyzed by the index (like one of the faceted _exact fields).
            Using a field that is analyzed will result in inaccurate counts, as analyzed fields are broken down by the
            search backend and will result in records being grouped by substrings of the aggregation_key field.
        """
        self.backend = backend
        self.aggregation_key = aggregation_key
        self.aggregation_name = 'distinct_{}'.format(aggregation_key)

    def search(self, query_string, **kwargs):
        """
        Run a search query and return the results.

        Re-implements the ElasticsearchSearchBackend.search method so that the logic necessary for computing
        and processing distinct hit and facet counts can be added in the appropriate places.
        """
        if len(query_string) == 0:
            return {
                'results': [],
                'hits': 0,
            }

        if not self.backend.setup_complete:
            self.backend.setup()

        # Call the custom build_search_kwargs method instead of the wrapped backend version so that aggregations
        # may be added to the query.
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
            raw_results = self.backend.conn.search(body=search_kwargs,
                                           index=self.backend.index_name,
                                           doc_type='modelresult',
                                           _source=True)
        except elasticsearch.TransportError as e:
            if not self.backend.silently_fail:
                raise

            self.backend.log.error('Failed to query Elasticsearch using "%s": %s', query_string, e, exc_info=True)
            raw_results = {}

        # Call the custom _process_results method instead of the wrapped backend version so that aggregations may
        # be processed correctly.
        return self._process_results(raw_results,
                                     highlight=kwargs.get('highlight'),
                                     result_class=kwargs.get('result_class', SearchResult),
                                     distance_point=kwargs.get('distance_point'),
                                     geo_sort=geo_sort)

    def build_search_kwargs(self, *args, **kwargs):
        """
        Build and return the arguments for the elasticsearch query.

        Overrides and re-implements the ElasticsearchSearchBackend.build_search_kwargs method so that
        aggregations may be added to compute distinct counts.

        Note: If this query includes facets, each facet will be converted to an aggregation
        and the facets clause will be removed.
        """
        search_kwargs = self.backend.build_search_kwargs(*args, **kwargs)

        # Setting precision to 1500 should result in a distinct hit count that is close to accurate
        # when the query returns fewer than 1500 search results. This may be increased (with a performance
        # penalty) when larger result sets become more common.
        aggregations = self._build_cardinality_aggregation(precision=1500)

        if search_kwargs.get('facets'):
            for facet_name, facet_config in search_kwargs['facets'].items():
                new_facet = self._convert_facet_to_aggregation(facet_config)

                # Setting precision to 1000 should result in a distinct hit count that is close to accurate
                # when the query returns fewer than 1000 search results. This may be increased (with a performance
                # penalty) when larger result sets become more common.
                new_facet['aggs'] = self._build_cardinality_aggregation(precision=1000)
                aggregations[facet_name] = new_facet
            del search_kwargs['facets']

        search_kwargs['aggs'] = aggregations

        return search_kwargs

    def _build_cardinality_aggregation(self, precision=None):
        """
        Build and return a cardinality aggregation using the configured aggregation_key.
        The elasticsearch cardinality aggregation does not guarantee accurate results. Accuracy
        is configurable via an optional precision_threshold argument. See
        https://www.elastic.co/guide/en/elasticsearch/reference/1.5/search-aggregations-metrics-cardinality-aggregation.html

        -- Parameters --
        precision - a numeric value below which counts computed by the cardinality aggregation can
            be expected to be close to accurate. Setting this value requires a memory tradeoff of
            about (precision * 8) bytes.
        """
        aggregation = {self.aggregation_name: {'cardinality': {'field': self.aggregation_key}}}
        if precision is not None:
            aggregation[self.aggregation_name]['cardinality']['precision_threshold'] = precision

        return aggregation

    def _convert_facet_to_aggregation(self, facet_config):
        """
        Convert an elasticsearch facet into an aggregation.

        Conversions are only supported for simple query and terms facets. An error will
        be raised if conversion is attempted for other types of facets. See the elasticsearch docs
        for information on converting other types of facets to aggregations.
        https://www.elastic.co/guide/en/elasticsearch/reference/1.5/search-facets-migrating-to-aggs.html
        """
        if len(facet_config.keys()) != 1:
            raise RuntimeError('Cannot convert facet to aggregation: Expected exactly 1 key in config.')

        if 'terms' in facet_config:
            return self._convert_terms_facet_to_aggregation(facet_config)
        elif 'query' in facet_config:
            return self._convert_query_facet_to_aggregation(facet_config)
        else:
            raise RuntimeError('Cannot convert facet to aggregation: Unsupported facet type.')

    def _convert_terms_facet_to_aggregation(self, facet_config):
        """
        Convert an elasticsearch terms facet to an aggregation.

        Only the 'field' and 'size' options are supported for conversion. If other options are present, an error
        will be raised. See the elasticsearch docs for more information on converting terms facets to aggregations.
        https://www.elastic.co/guide/en/elasticsearch/reference/1.5/search-facets-migrating-to-aggs.html#_simple_cases
        """
        supported_options = {'field', 'size'}
        for option, value in facet_config['terms'].items():
            if option not in supported_options:
                msg = 'Cannot convert terms facet to aggregation: Unsupported option ({})'.format(option)
                raise RuntimeError(msg)

        # In the simplest case, nothing needs to be done to convert a terms facet to an aggregation.
        return facet_config

    def _convert_query_facet_to_aggregation(self, facet_config):
        """
        Convert an elasticsearch query facet to an aggregation.

        The 'query_string' option is currently the only option supported for conversion. The 'query' option is the only
        option supported for conversion within the 'query_string' config. If other options are present, an error
        will be raised. See the elasticsearch docs for more information on converting query facets to aggregations.
        https://www.elastic.co/guide/en/elasticsearch/reference/1.5/search-facets-migrating-to-aggs.html#_query_facets
        """
        supported_query_options = {'query_string'}
        for option, value in facet_config['query'].items():
            if option not in supported_query_options:
                msg = 'Cannot convert query facet to aggregation: Unsupported option ({})'.format(option)
                raise RuntimeError(msg)

        supported_query_string_options = {'query'}
        for option, value in facet_config['query']['query_string'].items():
            if option not in supported_query_string_options:
                msg = 'Cannot convert query facet to aggregation: Unsupported query_string option ({})'.format(option)
                raise RuntimeError(msg)

        # In the simplest case, a query facet can be converted to an aggregation by wrapping it in a filter.
        return {'filter': facet_config}

    def _process_results(self, raw_results, **kwargs):
        """
        Construct and return a dictionary of query result information from the raw query results.

        Overrides and re-implements the ElasticsearchSearchBackend._process_results method so that
        the distinct count information may be extracted and included in the processed results dictionary.
        """
        results = self.backend._process_results(raw_results, **kwargs)
        aggs = raw_results['aggregations']

        # Process the distinct hit count
        results['distinct_hits'] = aggs[self.aggregation_name]['value']

        # Process the remaining aggregations, which should all be for facets.
        facets = {'fields': {}, 'dates': {}, 'queries': {}}
        for name, data in aggs.items():
            # The distinct hit count for the overall query was already processed.
            if name == self.aggregation_name:
                continue

            # Field facets:
            elif 'buckets' in data:
                buckets = data['buckets']
                facets['fields'][name] = [
                    # Extract the facet name, count, and distinct_count
                    (bucket['key'], bucket['doc_count'], bucket[self.aggregation_name]['value']) for bucket in buckets
                ]

            # Query facets:
            else:
                # Extract the facet name, count, and distinct_count
                facets['queries'][name] = (data['doc_count'], data[self.aggregation_name]['value'])

            results['facets'] = facets

        return results
