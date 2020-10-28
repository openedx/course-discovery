from django.conf import settings
from elasticsearch_dsl.connections import get_connection

from course_discovery.apps.edx_elasticsearch_dsl_extensions.response import DistinctDSLResponse
from course_discovery.apps.edx_elasticsearch_dsl_extensions.search import FacetedSearch


class DistinctCountsSearchQuerySet(FacetedSearch):
    """
    Extends original Faceted search.

    Computes and caches distinct hit and facet counts for a query.
    """

    def __init__(self, **kwargs):
        """
        Initialize a new instance of the DistinctCountsSearchQuerySet.
        """
        super(DistinctCountsSearchQuerySet, self).__init__(**kwargs)
        self.aggregation_key = None
        self._distinct_result_count = None

    # pylint: disable=arguments-differ
    def _clone(self, klass=None):
        """
        Clone Search class.

        Create and return a new DistinctCountsSearchQuery with fieldset
        to match those on the original object.
        """
        clone = super()._clone(klass=klass)
        if isinstance(clone, DistinctCountsSearchQuerySet):
            clone.aggregation_key = self.aggregation_key
            clone._distinct_result_count = self._distinct_result_count  # pylint: disable=protected-access

        return clone

    @staticmethod
    def from_queryset(queryset):
        """
        Builds DistinctCountsSearchQuerySet from an existing `Search` queryset.
        """
        queryset.__class__.with_distinct_counts = DistinctCountsSearchQuerySet.with_distinct_counts
        clone = queryset._clone()  # pylint: disable=protected-access
        return clone

    def with_distinct_counts(self, aggregation_key):
        """
        Adds distinct_count aggregations to the `Search`.

        Arguments:
            aggregation_key (str): The field that should be used to group records when computing distinct counts.
                It should be a field that is NOT analyzed by the index (like one of the faceted _exact fields).
                Using a field that is analyzed will result in inaccurate counts, as analyzed fields are broken down by
                the search backend and will result in records being grouped by substrings of the aggregation_key field.
        """
        clone = self._clone(klass=DistinctCountsSearchQuerySet)
        clone.aggregation_key = aggregation_key
        clone.validate()
        return clone

    def execute(self, ignore_cache=False):
        """
        Execute the query and cache the results.
        """
        # Make sure that the Query is valid before running it.
        self.validate()
        if ignore_cache or not hasattr(self, '_response'):
            search_query = self.to_dict()
            backend = DistinctCountsElasticsearchQueryWrapper(self, self.aggregation_key)
            self._response = backend.search(search_query)  # pylint: disable=attribute-defined-outside-init
            # Use the DistinctCountsElasticsearchQueryWrapper to execute the query so that distinct hit and query
            # counts may be computed.

            self._distinct_result_count = getattr(self._response, 'distinct_hits', 0)

        return self._response

    def validate(self):
        """
        Verify that all `FacetedSearch` options are valid and supported by this custom `FacetedSearch` class.
        """
        dicted_aggs = self.aggs.to_dict().get('aggs')
        if dicted_aggs:
            for agg_name, options in dicted_aggs.items():
                aggs = options.get('aggs')
                if aggs:
                    for field, agg_options in aggs.items():
                        if 'date_histogram' in agg_options.keys():
                            raise RuntimeError('DistinctCountsSearchQuerySet does not support date facets.')
                        self._validate_field_facet_options(field, agg_options)

        if self.aggregation_key is None:
            raise RuntimeError('aggregation_key is required.')

    def _validate_field_facet_options(self, field, options):
        """
        Verify that the provided field facet options are valid and can be converted to an aggregation.
        """
        supported_options = DistinctCountsElasticsearchQueryWrapper.SUPPORTED_FIELD_FACET_OPTIONS
        options_ = list(options.values())[0]
        for option, __ in options_.items():
            if option not in supported_options:
                msg = (
                    'DistinctCountsSearchQuerySet only supports a limited set of field facet options.'
                    'Field: {field}, Supported Options: ({supported}), Provided Options: ({provided})'
                ).format(field=field, supported=','.join(supported_options), provided=','.join(options.keys()))
                raise RuntimeError(msg)

    # pylint: disable=arguments-differ
    @classmethod
    def from_dict(cls, *args, **kwargs):
        """
        Raise an exception since we do not currently want/need to support raw queries.
        """
        raise RuntimeError('DistinctCountsSearchQuerySet does not support raw queries.')

    # pylint: disable=arguments-differ
    def update_from_dict(self, *args, **kwargs):
        """
        Raise an exception since we do not currently want/need to support raw queries.
        """
        raise RuntimeError('DistinctCountsSearchQuerySet does not support raw queries.')

    def distinct_count(self):
        """
        Return the distinct hit count.
        """

        if self._distinct_result_count is None:
            self.execute()
        return self._distinct_result_count

    def facet_counts(self):
        """
        Return the facet counts.
        """
        response = self.execute()

        return response.facets


class DistinctCountsElasticsearchQueryWrapper:
    """
    Elasticsearch `Search` class wrapper.

    Custom search-like class that enables the computation of distinct hit and facet counts during search queries.
    This class is not meant to be a true Search. It is meant to wrap an existing
    Search instance and expose a very limited subset of search functionality.
    """

    # The options that are supported for building field facet aggregations.
    SUPPORTED_FIELD_FACET_OPTIONS = {'field', 'size'}

    # The default size for field facet aggregations.
    DEFAULT_FIELD_FACET_SIZE = 100

    def __init__(self, search_instance, aggregation_key):
        """
        Initialize a new instance of the DistinctCountsElasticsearchQueryWrapper.

        Arguments:
            search_instance (Search)
            aggregation_key (str): The field that should be used to group records when computing distinct counts.
                It should be a field that is NOT analyzed by the index (like one of the faceted _exact fields).
                Using a field that is analyzed will result in inaccurate counts, as analyzed fields are broken down by
                the search instance and will result in records being grouped by substrings of the aggregation_key field.
        """
        self.search_instance = search_instance
        self.aggregation_key = aggregation_key
        self.aggregation_name = 'distinct_{}'.format(aggregation_key)

    def search(self, search_query):
        """
        Run a search query and return the results.
        """
        if not search_query:
            return {'results': [], 'hits': 0, 'distinct_hits': 0}

        self.search_instance.validate()
        search_kwargs = self._build_search_kwargs(**search_query)
        # pylint: disable=protected-access
        es = get_connection(self.search_instance._using)
        raw_results = es.search(index=self.search_instance._index, body=search_kwargs, **self.search_instance._params)

        return self._process_results(raw_results)

    def _build_search_kwargs(self, *args, **kwargs):  # pylint: disable=unused-argument
        """
        Build and return the arguments for the elasticsearch query.
        """
        aggregations = self._build_cardinality_aggregation(precision=settings.DISTINCT_COUNTS_HIT_PRECISION)
        facets = kwargs.get('aggs', {})
        field_facets = {key: value for key, value in facets.items() if key.startswith('_filter')}
        query_facets = {key: value for key, value in facets.items() if key.startswith('_query')}
        unhandled_facets = set(facets.keys()) - set(field_facets.keys()) - set(query_facets.keys())
        if field_facets:
            aggregations.update(
                self._build_field_facet_aggregations(
                    facet_dict=field_facets, precision=settings.DISTINCT_COUNTS_FACET_PRECISION
                )
            )

        if query_facets:
            aggregations.update(
                self._build_query_facet_aggregations(
                    facet_dict=query_facets, precision=settings.DISTINCT_COUNTS_FACET_PRECISION
                )
            )

        if unhandled_facets:
            raise RuntimeError(
                'DistinctCountsElasticsearchQueryWrapper does not support {} facets.'.format(unhandled_facets)
            )
        kwargs['aggs'] = aggregations

        return kwargs

    def _build_cardinality_aggregation(self, precision=None):
        """
        Builds and returns cardinality aggregation using configured aggregation_key.

        The elasticsearch cardinality aggregation does not guarantee accurate results.
        Accuracy is configurable via an optional precision_threshold argument.
        See
        https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-metrics-cardinality-aggregation.html

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
        """
        Build and return a dictionary of aggregations for field facets.
        """
        aggregations = {}
        for facet_field_name, opts in facet_dict.items():
            aggregations[facet_field_name] = {'aggregations': self._build_cardinality_aggregation(precision=precision)}
            aggregations[facet_field_name].update(list(opts.get('aggs').values())[0])
        return aggregations

    def _build_query_facet_aggregations(self, facet_dict, precision=None):
        """
        Build and return a dictionary of aggregations for query facets.
        """
        aggregations = {}
        for facet_field_name, value in facet_dict.items():
            aggregations[facet_field_name] = {
                'filter': value.get('filter'),
                'aggs': self._build_cardinality_aggregation(precision=precision),
            }
        return aggregations

    def _process_results(self, raw_results, **kwargs):  # pylint: disable=unused-argument
        """
        Process the query results into a form that is more easily consumable by the client.
        """
        raw_results['aggregations']['aggregation_name'] = self.aggregation_name
        results = DistinctDSLResponse(self.search_instance, raw_results)
        aggregations = raw_results['aggregations']
        # Process the distinct hit count
        # pylint: disable=literal-used-as-attribute
        setattr(results, 'distinct_hits', aggregations[self.aggregation_name]['value'])

        return results
