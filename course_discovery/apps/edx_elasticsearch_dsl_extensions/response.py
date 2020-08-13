from elasticsearch_dsl.response import AggResponse
from elasticsearch_dsl.response import Response as OriginResponse
from elasticsearch_dsl.utils import AttrDict


class FacetResponse(AggResponse):
    """
    Custom facet response

    Proveds default elasticsearch-eds aggregation to drf-haystack format.
    Implemented to support backward compatibility with drf-haystack lib.

    The format is:
        {'fields': {}, 'dates': {}, 'queries': {}}
    """
    def __init__(self, aggs, search, data):
        data_ = self._process_aggs_results(data)
        super(FacetResponse, self).__init__(aggs, search, data_)

    @staticmethod
    def _process_aggs_results(raw_results):
        facets = {'fields': {}, 'dates': {}, 'queries': {}}
        for field_name, data in raw_results.items():
            if field_name.startswith('_filter'):
                for i in data:
                    if i in field_name:
                        exact_field_name = i
                        facets['fields'][exact_field_name] = [
                            (bucket['key'], bucket['doc_count']) for bucket in data[exact_field_name]['buckets']
                        ]
                        break
            elif field_name.startswith('_query'):
                *_, exact_field_name = field_name.partition('query_')
                facets['queries'][exact_field_name] = data['doc_count']
        return facets


class DistinctFacetResponse(FacetResponse):
    @staticmethod
    def _process_aggs_results(raw_results):
        facets = {'fields': {}, 'dates': {}, 'queries': {}}
        aggregation_name = raw_results.pop('aggregation_name')
        for field_name, data in raw_results.items():
            if field_name == aggregation_name:
                continue

            if field_name.startswith('_filter'):
                *_, exact_field_name = field_name.partition('filter_')
                facets['fields'][exact_field_name] = [
                    (bucket['key'], bucket['doc_count'], bucket[aggregation_name]['value'])
                    for bucket in data['buckets']
                ]
            elif field_name.startswith('_query'):
                *_, exact_field_name = field_name.partition('query_')
                facets['queries'][exact_field_name] = (data['doc_count'], data[aggregation_name]['value'])
        return facets


class DSLResponse(OriginResponse):
    """
    Custom elasticsearch dsl response.

    Extends facet property as custom `FacetResponse`
    """
    facet_response_class = FacetResponse

    @property
    def facets(self):
        if not hasattr(self, '_facets'):
            facets = self.facet_response_class(self._search.aggs, self._search, self._d_.get('aggregations', {}))
            # avoid assigning _facets into self._d_
            super(AttrDict, self).__setattr__('_facets', facets)  # pylint: disable=bad-super-call

        return self._facets


class DistinctDSLResponse(DSLResponse):
    facet_response_class = DistinctFacetResponse
