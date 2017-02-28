from haystack.query import SearchQuerySet
from course_discovery.apps.edx_haystack_extensions.distinct_counts.backends import DistinctCountsSearchQuery


class DistinctCountsSearchQuerySet(SearchQuerySet):
    """Custom SearchQuerySet class that can compute and cache distinct hit and facet counts for a query."""

    @staticmethod
    def from_queryset(queryset):
        """ Builds a DistinctCountsSearchQuerySet from an existing SearchQuerySet."""
        return queryset._clone(klass=DistinctCountsSearchQuerySet)  # pylint: disable=protected-access

    def __init__(self, **kwargs):
        """
        Initialize a new instance of the DistinctCountsSearchQuerySet.

        Overrides SearchQuerySet.__init__ from:
        https://github.com/django-haystack/django-haystack/blob/v2.5.0/haystack/query.py#L24
        """
        super(DistinctCountsSearchQuerySet, self).__init__(**kwargs)
        self._distinct_result_count = None

    def with_distinct_counts(self, aggregation_key):
        """
        Adds distinct_count aggregations to the Query.

        Arguments:
            aggregation_key (str): The field that should be used to group records when computing distinct counts.
                It should be a field that is NOT analyzed by the index (like one of the faceted _exact fields).
                Using a field that is analyzed will result in inaccurate counts, as analyzed fields are broken down by
                the search backend and will result in records being grouped by substrings of the aggregation_key field.
        """
        clone = self._clone()
        clone.query = clone.query._clone(DistinctCountsSearchQuery)  # pylint: disable=protected-access
        clone.query.aggregation_key = aggregation_key
        clone.query.validate()
        return clone

    def distinct_count(self):
        """
        Return the distinct hit count.

        Note: This will raise an error if the SearchQuerySet has not been configured to compute distinct counts. It
        will also force the query to run if it hasn't already.
        """
        if not isinstance(self.query, DistinctCountsSearchQuery):
            raise RuntimeError('This SearchQuerySet has not been configured to compute distinct counts.')

        if self._distinct_result_count is None:
            self._distinct_result_count = self.query.get_distinct_count()
        return self._distinct_result_count
