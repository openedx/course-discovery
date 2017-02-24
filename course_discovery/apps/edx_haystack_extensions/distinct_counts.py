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
    def __init__(self, **kwargs):
        super(DistinctCountsSearchQuery, self).__init__(**kwargs)
        self._aggregation_key = None
        self._distinct_hit_count = None

    def _clone(self, **kwargs):
        clone = super(DistinctCountsSearchQuery, self)._clone(**kwargs)
        clone._aggregation_key = self._aggregation_key
        clone._distinct_hit_count = self._distinct_hit_count
        return clone

    def run(self, spelling_query=None, **kwargs):
        if not self._aggregation_key:
            raise RuntimeError('DistinctCountsSearchQuery cannot run without aggregation_key.')

        final_query = self.build_query()
        search_kwargs = self.build_params(spelling_query=spelling_query)

        if kwargs:
            search_kwargs.update(kwargs)

        backend = DistinctCountsElasticsearchBackend(self.backend, self._aggregation_key)
        results = backend.search(final_query, **search_kwargs)

        self._results = results.get('results', [])
        self._hit_count = results.get('hits', 0)
        self._distinct_hit_count = results.get('distinct_hits', 0)
        self._facet_counts = self.post_process_facets(results)
        self._spelling_suggestion = results.get('spelling_suggestion', None)

    def run_mlt(self, **kwargs):
        raise NotImplemented('DistinctCountsSearchQuery.run_mlt is not supported.')

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
    def __init__(self, backend, aggregation_key):
        self.backend = backend
        self.aggregation_key = aggregation_key
        self.aggregation_name = 'distinct_{}'.format(aggregation_key)

    def search(self, query_string, **kwargs):
        if len(query_string) == 0:
            return {
                'results': [],
                'hits': 0,
            }

        if not self.backend.setup_complete:
            self.backend.setup()

        # Override
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

        # Override
        return self._process_results(raw_results,
                                     highlight=kwargs.get('highlight'),
                                     result_class=kwargs.get('result_class', SearchResult),
                                     distance_point=kwargs.get('distance_point'),
                                     geo_sort=geo_sort)

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
                    # Note: Setting to 40000, which is the maximum supported value. See
                    # https://www.elastic.co/guide/en/elasticsearch/reference/1.5/search-aggregations-metrics-cardinality-aggregation.html
                    'precision_threshold': 40000
                }
            }
        }

    def _convert_facet_to_aggregation(self, facet_config):
        # Only allow the simplest of facet types to be converted for now.
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

        # If 'field' and 'size' are the only options present in the config, we shouldn't need to do anything
        # to convert to a terms facet to an aggregation See:
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

        # To convert a simple query facet to an aggregation, all we should need to do is wrap it in a filter. See:
        # https://www.elastic.co/guide/en/elasticsearch/reference/1.5/search-facets-migrating-to-aggs.html#_query_facets
        return {'filter': facet_config}

    def _process_results(self, raw_results, **kwargs):
        results = self.backend._process_results(raw_results, **kwargs)

        aggs = raw_results['aggregations']
        results['distinct_hits'] = aggs[self.aggregation_name]['value']

        # All of the remaining aggregations should be for facets
        facets = {'fields': {}, 'dates': {}, 'queries': {}}
        for name, data in aggs.items():
            if name == self.aggregation_name:
                continue
            elif 'buckets' in data:
                buckets = data['buckets']
                facets['fields'][name] = [
                    (bucket['key'], bucket['doc_count'], bucket[self.aggregation_name]['value']) for bucket in buckets
                ]
            else:
                facets['queries'][name] = (data['doc_count'], data[self.aggregation_name]['value'])

            results['facets'] = facets

        return results
