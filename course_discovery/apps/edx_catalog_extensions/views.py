from course_discovery.apps.api.v1.views.search import AggregateSearchViewSet
from course_discovery.apps.edx_catalog_extensions.serializers import DistinctCountsAggregateFacetSearchSerializer
from course_discovery.apps.edx_haystack_extensions.distinct_counts.query import DistinctCountsSearchQuerySet


class DistinctCountsAggregateSearchViewSet(AggregateSearchViewSet):
    """
    Provides a facets endpoint that returns distinct hit and facet counts with the rest of the query results.
    
    This ViewSet only exposes a single endpoint, `/search/all/facets`, which should be functionally identical to the
    AggregateSearchViewSet facets endpoint except that it also include distinct hit and facet counts. The other
    AggregateSearchViewSet endpoints (list, etc) are not exposed here.
    """

    # Use DistinctCountsAggregateFacetSearchSerializer so that the distinct counts may be returned with the response.
    facet_serializer_class = DistinctCountsAggregateFacetSearchSerializer

    def filter_facet_queryset(self, queryset):
        """
        Return the queryset that should be used to generate the result set.

        Overrides BaseHaystackViewSet.filter_facet_queryset so that the returned queryset may be wrapped in a 
        DistinctCountsSearchQuerySet, which supports the ability to compute distinct hit and facet counts.
        """
        new_queryset = super(DistinctCountsAggregateSearchViewSet, self).filter_facet_queryset(queryset)
        return DistinctCountsSearchQuerySet.from_queryset(new_queryset, 'aggregation_key')

    def facets(self, request):
        """
        Returns faceted search results
        ---
        parameters:
            - name: q
              description: Search text
              paramType: query
              type: string
              required: false
            - name: selected_facets
              description: Field facets
              paramType: query
              allowMultiple: true
              type: array
              items:
                pytype: str
              required: false
            - name: selected_query_facets
              description: Query facets
              paramType: query
              allowMultiple: true
              type: array
              items:
                pytype: str
              required: false
        """
        return super(DistinctCountsAggregateSearchViewSet, self).facets(request)

    def list(self, request):
        """
        Raise NotImplemented, as this endpoint is not currently supported.
        """
        raise NotImplemented('The list endpoint is not supported for this ViewSet.')
