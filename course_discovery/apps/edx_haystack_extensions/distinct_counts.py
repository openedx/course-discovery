import elasticsearch

from drf_haystack.serializers import FacetFieldSerializer
from haystack.backends.elasticsearch_backend import ElasticsearchSearchQuery
from haystack.models import SearchResult
from haystack.query import SearchQuerySet
from rest_framework import serializers
from rest_framework.fields import DictField
from drf_haystack.fields import FacetDictField, FacetListField

from course_discovery.apps.api.serializers import BaseHaystackFacetSerializer, AggregateFacetSearchSerializer, QueryFacetFieldSerializer


class DistinctCountsAggregateFacetSearchSerializer(AggregateFacetSearchSerializer):
    def get_fields(self):
        field_data = self.instance.pop('fields', {})
        query_data = self.format_query_facet_data(self.instance.pop('queries', {}))

        field_mapping = super(DistinctCountsAggregateFacetSearchSerializer, self).get_fields()
        field_mapping['fields'] = FacetDictField(
            child=FacetListField(child=DistinctCountsFacetFieldSerializer(field_data), required=False)
        )
        field_mapping['queries'] = DictField(
            query_data,
            child=DistinctCountsQueryFacetFieldSerializer(),
            required=False
        )

        if self.serialize_objects:
            field_mapping.move_to_end('objects')

        self.instance['fields'] = field_data
        self.instance['queries'] = query_data

        return field_mapping

    def get_objects(self, instance):
        data = super(DistinctCountsAggregateFacetSearchSerializer, self).get_objects(instance)
        data['distinct_count'] = self.context['objects'].distinct_count()
        return data

    def format_query_facet_data(self, query_facet_counts):
        query_data = {}
        for field, options in getattr(self.Meta, 'field_queries', {}).items():  # pylint: disable=no-member
            counts = query_facet_counts.get(field, (0, 0))
            if counts[0]:
                query_data[field] = {
                    'field': field,
                    'options': options,
                    'count': counts[0],
                    'distinct_count': counts[1],
                }
        return query_data

class DistinctCountsFacetFieldSerializer(FacetFieldSerializer):
    distinct_count = serializers.SerializerMethodField()

    def get_distinct_count(self, instance):
        count = instance[2]
        return serializers.IntegerField(read_only=True).to_representation(count)


class DistinctCountsQueryFacetFieldSerializer(QueryFacetFieldSerializer):
    distinct_count = serializers.SerializerMethodField()

    def get_distinct_count(self, instance):
        count = instance['distinct_count']
        return serializers.IntegerField(read_only=True).to_representation(count)


class DistinctCountsSearchQuerySet(SearchQuerySet):
    @staticmethod
    def from_queryset(queryset):
        new_queryset = queryset._clone(klass=DistinctCountsSearchQuerySet)
        new_queryset.query = new_queryset.query._clone(klass=DistinctCountsSearchQuery)
        return new_queryset

    def __init__(self, **kwargs):
        super(DistinctCountsSearchQuerySet, self).__init__(**kwargs)
        self._distinct_result_count = None

    def distinct_count(self):
        if self._distinct_result_count is None:
            self._distinct_result_count = self.query.get_distinct_count()
        return self._distinct_result_count

    def set_aggregation_key(self, aggregation_key):
        clone = self._clone()
        clone.query.set_aggregation_key(aggregation_key)
        return clone


class DistinctCountsSearchQuery(ElasticsearchSearchQuery):
    """
    Custom Haystack Query class designed to allow for the computation and exposure of distinct hit and facet counts.
    """

    def __init__(self, **kwargs):
        super(DistinctCountsSearchQuery, self).__init__(**kwargs)
        self._aggregation_key = None
        self._distinct_hit_count = None

    # Override of ElasticsearchSearchQuery._clone
    #
    # Here, we need to make sure the aggregation_key and distinct_hit_count fields, which do not exist on
    # the superclass, are set correctly on the cloned object.
    def _clone(self, **kwargs):
        clone = super(DistinctCountsSearchQuery, self)._clone(**kwargs)
        clone._aggregation_key = self._aggregation_key
        clone._distinct_hit_count = self._distinct_hit_count
        return clone

    # Override of ElasticesearchSearchQuery.run
    #
    # Most of the code here is the same as the superclass version, except we do not allow queries that have
    # not set an aggregation_key, and we need to make sure to execute the query using our 
    # custom DistinctCountsElasticsearchBackend and save the distinct_hit_count.
    def run(self, spelling_query=None, **kwargs):
        # This query class should only be used when we want to retrieve distinct counts. We cannot compute distinct
        # counts without an aggregation_key.
        if not self._aggregation_key:
            raise RuntimeError('DistinctCountsSearchQuery cannot run without aggregation_key.')

        final_query = self.build_query()
        search_kwargs = self.build_params(spelling_query=spelling_query)

        if kwargs:
            search_kwargs.update(kwargs)

        # In order to compute distinct counts, we need to use our custom backend wrapper.
        backend = DistinctCountsElasticsearchBackend(self.backend, self._aggregation_key)
        results = backend.search(final_query, **search_kwargs)

        self._results = results.get('results', [])
        self._hit_count = results.get('hits', 0)
        self._distinct_hit_count = results.get('distinct_hits', 0)
        self._facet_counts = self.post_process_facets(results)
        self._spelling_suggestion = results.get('spelling_suggestion', None)

    # We have not implemented support for distinct counts with more-like-this queries. Therefore we should
    # fail loudly if this is called.
    def run_mlt(self, **kwargs):
        raise NotImplemented('DistinctCountsSearchQuery.run_mlt is not supported.')

    # We have not implemented support for distinct counts with raw queries. Therefore we should
    # fail loudly if this is called.
    def run_raw(self, **kwargs):
        raise NotImplemented('DistinctCountsSearchQuery.run_raw is not supported.')

    def set_aggregation_key(self, aggregation_key):
        self._aggregation_key = aggregation_key

    def get_distinct_count(self):
        if self._distinct_hit_count is None:
            # Calling get_count will cause the query to run and both count and distinct_count to be
            # populated
            self.get_count()
        return self._distinct_hit_count


class DistinctCountsElasticsearchBackend(object):
    """
    Custom backend designed specifically to allow for the computation of distinct hit and facet counts
    during search queries.

    This is not a true ElasticsearchSearchBackend as it does not inherit from that class. It wraps an
    ElasticsearchSearchBackend instance and exposes a very limited subset of the normal backend functionality.
    """
    def __init__(self, backend, aggregation_key):
        """
        backend - an ElasticsearchSearchBackend instance
        aggregation_key - a string specifying the field that should be used in the cardinality aggregation functions
            to compute distinct counts. For example, if you want to search across course_runs and get the count of
            distinct courses represented in the result set, you could set aggregation_key to 'course_key_exact'. Note
            that the aggregation_key should be a field that is not tokenized by the search engine (like the _exact
            versions of faceted fields).
        """
        self.backend = backend
        self.aggregation_key = aggregation_key
        self.aggregation_name = 'distinct_{}'.format(aggregation_key)

    # Override of haystack's ElasticsearchSearchBackend.search method.
    #
    # Most of the code here is the same as in the original, except that some method calls need to be delegated to the
    # wrapped backend instance.
    def search(self, query_string, **kwargs):
        if not (self.aggregation_key and self.aggregation_name):
            raise RuntimeError('DistinctCounts search cannot be executed without aggregation_key and aggregation_name.')

        if len(query_string) == 0:
            return {
                'results': [],
                'hits': 0,
            }

        if not self.backend.setup_complete:
            self.backend.setup()

        # Call the overridden version of build_search_kwargs instead of the wrapped backend version.
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

            self.backend.log.error("Failed to query Elasticsearch using '%s': %s", query_string, e, exc_info=True)
            raw_results = {}

        # Call the overridden version of _process_results instead of the wrapped backend version.
        return self._process_results(raw_results,
                                     highlight=kwargs.get('highlight'),
                                     result_class=kwargs.get('result_class', SearchResult),
                                     distance_point=kwargs.get('distance_point'),
                                     geo_sort=geo_sort)

    # Override of haystack's ElasticsearchSearchBackend.build_search_kwargs method.
    #
    # Here we call the original version of that method on the wrapped backend instance, then extend the returned
    # result to include a cardinality aggregation to compute the distinct hit count. If the returned result contains
    # facets, we convert them to aggregations and add an additional cardinality aggregation to each one to compute
    # distinct counts.
    def build_search_kwargs(self, *args, **kwargs):
        search_kwargs = self.backend.build_search_kwargs(*args, **kwargs)

        aggregations = self._cardinality_aggregation()

        if search_kwargs.get('facets'):
            for facet_name, facet_config in search_kwargs['facets'].items():
                new_facet = self._convert_facet_to_aggregation(facet_config)
                new_facet['aggs'] = self._cardinality_aggregation()
                aggregations[facet_name] = new_facet
            del search_kwargs['facets']

        search_kwargs['aggs'] = aggregations

        return search_kwargs

    def _cardinality_aggregation(self):
        return {
            self.aggregation_name: {
                'cardinality': {
                    'field': self.aggregation_key,

                    # The cardinality aggregation does not guarentee accurate results.
                    # The precision_threshold option allows us to define a value below which
                    # counts can be expected to be close to accurate. This requires additional memory
                    # usage of about (n * 8) bytes, where n is the value for precision_threshold. Since
                    # we only currently have around 5000 or so documents in our index, this shouldn't be
                    # a problem.
                    #
                    # Setting to 40000, which is the maximum supported value. See
                    # https://www.elastic.co/guide/en/elasticsearch/reference/1.5/search-aggregations-metrics-cardinality-aggregation.html
                    'precision_threshold': 40000
                }
            }
        }

    # Convert the facet to an aggregation.
    #
    # For now, we only support the conversion of the simplest of facets to aggregations. If we run a query
    # with other types of facets, this method will raise an exception. See the elasticsearch docs for info on migrating
    # from facets to aggregations.
    # https://www.elastic.co/guide/en/elasticsearch/reference/1.5/search-facets-migrating-to-aggs.html
    def _convert_facet_to_aggregation(self, facet_config):
        if len(facet_config.keys()) != 1:
            raise RuntimeError('Cannot convert facet to aggregation: Expected exactly 1 key in config.')

        if 'terms' in facet_config:
            return self._convert_terms_facet_to_aggregation(facet_config)
        elif 'query' in facet_config:
            return self._convert_query_facet_to_aggregation(facet_config)
        else:
            raise RuntimeError('Cannot convert facet to aggregation: Unsupported facet type ({})'.format(facet_type))

    def _convert_terms_facet_to_aggregation(self, facet_config):
        supported_options = {'field', 'size'}
        for option, value in facet_config['terms'].items():
            if option not in supported_options:
                msg = 'Cannot convert terms facet to aggregation: Unsupported option ({})'.format(option)
                raise RuntimeError(message)

        # In the simplest case, nothing needs to be done to convert a terms facet to an aggregation. See:
        # https://www.elastic.co/guide/en/elasticsearch/reference/1.5/search-facets-migrating-to-aggs.html#_simple_cases
        # https://www.elastic.co/guide/en/elasticsearch/reference/1.5/search-aggregations-bucket-terms-aggregation.html#_size
        return facet_config

    def _convert_query_facet_to_aggregation(self, facet_config):
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

        # In the simplest case, a query facet can be converted to an aggregation by wrapping it in a filter. See:
        # https://www.elastic.co/guide/en/elasticsearch/reference/1.5/search-facets-migrating-to-aggs.html#_query_facets
        return {'filter': facet_config}

    # Override of haystack's ElasticsearchSearchBackend._process_results method.
    #
    # Here we call the original version of that method on the wrapped backend instance, then extend the returned
    # result to include the distinct hit count and facet information.
    def _process_results(self, raw_results, **kwargs):
        results = self.backend._process_results(raw_results, **kwargs)

        # This backend is designed to only support queries with distinct count aggregations. Therefore, we can
        # expect the result set to always include at least one aggregation containing the distinct hit count.
        aggs = raw_results['aggregations']
        results['distinct_hits'] = aggs[self.aggregation_name]['value']

        # Process the remaining aggregations, which should all be for facets
        facets = {'fields': {}, 'dates': {}, 'queries': {}}
        for name, data in aggs.items():
            # The distinct hit count for the overall query
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
