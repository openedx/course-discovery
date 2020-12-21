import elasticsearch
from django.conf import settings
from haystack.backends.elasticsearch_backend import ElasticsearchSearchQuery
from haystack.models import SearchResult


class DistinctCountsSearchQuery(ElasticsearchSearchQuery):
    """ Custom Haystack Query class that computes and caches distinct hit and facet counts for a query."""

    def __init__(self, **kwargs):
        """
        Create and return a new instance of DistinctCountsSearchQuery.

        Overrides BaseSearchQuery.__init__ from:
        https://github.com/django-haystack/django-haystack/blob/v2.5.0/haystack/backends/__init__.py#L443
        """
        super().__init__(**kwargs)
        self.aggregation_key = None
        self._distinct_hit_count = None

    def _clone(self, klass=None, using=None):
        """
        Create and return a new DistinctCountsSearchQuery with fields set to match those on the original object.

        Overrides BaseSearchQuery._clone from:
        https://github.com/django-haystack/django-haystack/blob/v2.5.0/haystack/backends/__init__.py#L981
        """
        clone = super()._clone(klass=klass, using=using)
        if isinstance(clone, DistinctCountsSearchQuery):
            clone.aggregation_key = self.aggregation_key
            clone._distinct_hit_count = self._distinct_hit_count  # pylint: disable=protected-access
        return clone

    def get_distinct_count(self):
        """
        Return the distinct hit count for this query. Calling this method will cause the query to execute if
        it hasn't already been run.
        """
        if self._distinct_hit_count is None:
            self.run()
        return self._distinct_hit_count

    def run(self, spelling_query=None, **kwargs):
        """
        Run the query and cache the results.

        Overrides and re-implements ElasticsearchSearchQuery.run from:
        https://github.com/django-haystack/django-haystack/blob/v2.5.0/haystack/backends/elasticsearch_backend.py#L941
        """
        # Make sure that the Query is valid before running it.
        self.validate()

        final_query = self.build_query()
        search_kwargs = self.build_params(spelling_query)

        if kwargs:
            search_kwargs.update(kwargs)

        # Use the DistinctCountsElasticsearchBackendWrapper to execute the query so that distinct hit and query
        # counts may be computed.
        backend = DistinctCountsElasticsearchBackendWrapper(self.backend, self.aggregation_key)
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

        if self.aggregation_key is None:
            raise RuntimeError('aggregation_key is required.')

    def _validate_field_facet_options(self, field, options):
        """ Verify that the provided field facet options are valid and can be converted to an aggregation."""
        supported_options = DistinctCountsElasticsearchBackendWrapper.SUPPORTED_FIELD_FACET_OPTIONS
        for option, __ in options.items():
            if option not in supported_options:
                msg = (
                    'DistinctCountsSearchQuery only supports a limited set of field facet options.'
                    'Field: {field}, Supported Options: ({supported}), Provided Options: ({provided})'
                ).format(field=field, supported=','.join(supported_options), provided=','.join(options.keys()))
                raise RuntimeError(msg)

    def more_like_this(self, _model_instance):
        """ Raise an exception since we do not currently want/need to support more_like_this queries."""
        raise RuntimeError('DistinctCountsSearchQuery does not support more_like_this queries.')

    def run_mlt(self, **_kwargs):
        """ Raise an exception since we do not currently want/need to support more_like_this queries."""
        raise RuntimeError('DistinctCountsSearchQuery does not support more_like_this queries.')

    def raw_search(self, _query_string, **_kwargs):
        """ Raise an exception since we do not currently want/need to support raw queries."""
        raise RuntimeError('DistinctCountsSearchQuery does not support raw queries.')

    def run_raw(self, **_kwargs):
        """ Raise an exception since we do not currently want/need to support raw queries."""
        raise RuntimeError('DistinctCountsSearchQuery does not support raw queries.')

    def add_date_facet(self, _field, _start_date, _end_date, _gap_by, _gap_amount=1):
        """ Raise an exception since we do not currently want/need to support date facets."""
        raise RuntimeError('DistinctCountsSearchQuery does not support date facets.')

    def add_field_facet(self, field, **options):
        """
        Add a field facet to the Query. Raise an error if any unsupported options are provided.

        Overrides BaseSearchQuery.add_field_facet from:
        https://github.com/django-haystack/django-haystack/blob/v2.5.0/haystack/backends/__init__.py#L897
        """
        self._validate_field_facet_options(field, options)
        return super().add_field_facet(field, **options)


class DistinctCountsElasticsearchBackendWrapper:
    """
    Custom backend-like class that enables the computation of distinct hit and facet counts during search queries.
    This class is not meant to be a true ElasticsearchSearchBackend. It is meant to wrap an existing
    ElasticsearchSearchBackend instance and expose a very limited subset of backend functionality.
    """

    # The options that are supported for building field facet aggregations.
    SUPPORTED_FIELD_FACET_OPTIONS = {'size'}

    # The default size for field facet aggregations. This is the same value used by haystack.
    DEFAULT_FIELD_FACET_SIZE = 100

    def __init__(self, backend, aggregation_key):
        """
        Initialize a new instance of the DistinctCountsElasticsearchBackendWrapper.

        Arguments:
            backend (ElasticsearchSearchBackend)
            aggregation_key (str): The field that should be used to group records when computing distinct counts.
                It should be a field that is NOT analyzed by the index (like one of the faceted _exact fields).
                Using a field that is analyzed will result in inaccurate counts, as analyzed fields are broken down by
                the search backend and will result in records being grouped by substrings of the aggregation_key field.
        """
        self.backend = backend
        self.aggregation_key = aggregation_key
        self.aggregation_name = f'distinct_{aggregation_key}'

    def search(self, query_string, **kwargs):
        """
        Run a search query and return the results.

        Re-implements ElasticsearchSearchBackend.search from:
        https://github.com/django-haystack/django-haystack/blob/v2.5.0/haystack/backends/elasticsearch_backend.py#L495
        """
        if not query_string:
            return {'results': [], 'hits': 0, 'distinct_hits': 0}

        # NOTE (CCB): Haystack by default attempts to read/update the index mapping. Given that our mapping doesn't
        # frequently change, this is a waste of three API calls. Stop it! We set our mapping when we create the index.
        self.backend.setup_complete = True

        search_kwargs = self._build_search_kwargs(query_string, **kwargs)
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
            raw_results = self.backend.conn.search(
                body=search_kwargs,
                index=self.backend.index_name,
                doc_type='modelresult',
                _source=True
            )
        except elasticsearch.TransportError as e:
            if not self.backend.silently_fail:
                raise

            self.backend.log.error('Failed to query Elasticsearch using "%s": %s', query_string, e, exc_info=True)
            raw_results = {}

        return self._process_results(raw_results,
                                     highlight=kwargs.get('highlight'),
                                     result_class=kwargs.get('result_class', SearchResult),
                                     distance_point=kwargs.get('distance_point'),
                                     geo_sort=geo_sort)

    def _build_search_kwargs(self, *args, **kwargs):
        """ Build and return the arguments for the elasticsearch query."""
        aggregations = self._build_cardinality_aggregation(precision=settings.DISTINCT_COUNTS_HIT_PRECISION)

        if 'facets' in kwargs:
            aggregations.update(self._build_field_facet_aggregations(
                facet_dict=kwargs.pop('facets', {}),
                precision=settings.DISTINCT_COUNTS_FACET_PRECISION
            ))

        if 'query_facets' in kwargs:
            aggregations.update(self._build_query_facet_aggregations(
                facet_list=kwargs.pop('query_facets', []),
                precision=settings.DISTINCT_COUNTS_FACET_PRECISION
            ))

        if 'date_facets' in kwargs:
            raise RuntimeError('DistinctCountsElasticsearchBackendWrapper does not support date facets.')

        search_kwargs = self.backend.build_search_kwargs(*args, **kwargs)
        search_kwargs['aggregations'] = aggregations
        return search_kwargs

    def _build_cardinality_aggregation(self, precision=None):
        """
        Build and return a cardinality aggregation using the configured aggregation_key.
        The elasticsearch cardinality aggregation does not guarantee accurate results. Accuracy
        is configurable via an optional precision_threshold argument. See
        https://www.elastic.co/guide/en/elasticsearch/reference/1.5/search-aggregations-metrics-cardinality-aggregation.html

        Arguments:
            precision (str): a numeric value below which counts computed by the cardinality aggregation can
                be expected to be close to accurate. Setting this value requires a memory tradeoff of
                about (precision * 8) bytes.
        """
        aggregation = {self.aggregation_name: {'cardinality': {'field': self.aggregation_key}}}
        if precision is not None:
            aggregation[self.aggregation_name]['cardinality']['precision_threshold'] = precision
        return aggregation

    def _build_field_facet_aggregations(self, facet_dict, precision=None):
        """ Build and return a dictionary of aggregations for field facets."""
        aggregations = {}
        for facet_fieldname, opts in facet_dict.items():
            for opt, __ in opts.items():
                if opt not in self.SUPPORTED_FIELD_FACET_OPTIONS:
                    opts_str = ','.join(opts.keys())
                    msg = f'Cannot build aggregation for field facet with unsupported options: {opts_str}'
                    raise RuntimeError(msg)

            aggregations[facet_fieldname] = {
                'terms': {'field': facet_fieldname, 'size': opts.get('size', self.DEFAULT_FIELD_FACET_SIZE)},
                'aggregations': self._build_cardinality_aggregation(precision=precision),
            }
        return aggregations

    def _build_query_facet_aggregations(self, facet_list, precision=None):
        """ Build and return a dictionary of aggregations for query facets."""
        aggregations = {}
        for facet_fieldname, value in facet_list:
            aggregations[facet_fieldname] = {
                'filter': {'query': {'query_string': {'query': value}}},
                'aggregations': self._build_cardinality_aggregation(precision=precision),
            }
        return aggregations

    def _process_results(self, raw_results, **kwargs):
        """ Process the query results into a form that is more easily consumable by the client."""
        results = self.backend._process_results(raw_results, **kwargs)  # pylint: disable=protected-access
        aggregations = raw_results['aggregations']

        # Process the distinct hit count
        results['distinct_hits'] = aggregations[self.aggregation_name]['value']

        # Process the remaining aggregations, which should all be for facets.
        facets = {'fields': {}, 'dates': {}, 'queries': {}}
        for name, data in aggregations.items():

            # The distinct hit count for the overall query was already processed.
            if name == self.aggregation_name:
                continue

            # Field facets:
            if 'buckets' in data:
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
