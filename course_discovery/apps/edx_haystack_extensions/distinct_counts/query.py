from haystack.query import SearchQuerySet


class DistinctCountsSearchQuerySet(SearchQuerySet):
    """Custom SearchQuerySet class that computes and caches distinct hit and facet counts for a query."""

    @staticmethod
    def from_queryset(queryset, aggregation_key):
        """
        Build and return a properly configured DistinctCountsSearchQuerySet from an existing SearchQuerySet.

        -- Parameters -- 
        queryset - A SearchQuerySet instance.
        aggregation_key - The field that should be used to group records when computing distinct counts. 
            It should be a field that is NOT analyzed by the index (like one of the faceted _exact fields).
            Using a field that is analyzed will result in inaccurate counts, as analyzed fields are broken down by the 
            search backend and will result in records being grouped by substrings of the aggregation_key field.
        """
        new_queryset = queryset._clone(klass=DistinctCountsSearchQuerySet)
        new_queryset.query = new_queryset.query._clone(klass=DistinctCountsSearchQuery)
        new_queryset.query.set_aggregation_key(aggregation_key)
        return new_queryset

    def __init__(self, **kwargs):
        """
        Initialize a new instance of the DistinctCountsSearchQuerySet.

        Overrides SearchQuerySet.__init__ to make sure that the _distinct_result_count property
        is initialized.
        """
        super(DistinctCountsSearchQuerySet, self).__init__(**kwargs)
        self._distinct_result_count = None

    def distinct_count(self):
        """
        Return the distinct hit count.

        Note: This will cause the query to run if it hasn't already.
        """
        if self._distinct_result_count is None:
            self._distinct_result_count = self.query.get_distinct_count()
        return self._distinct_result_count
