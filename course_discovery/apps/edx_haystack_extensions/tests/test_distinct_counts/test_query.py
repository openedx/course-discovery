import datetime
import pytest

from django.test import TestCase
from haystack.query import SearchQuerySet

from course_discovery.apps.edx_haystack_extensions.distinct_counts.query import DistinctCountsSearchQuerySet
from course_discovery.apps.edx_haystack_extensions.distinct_counts.backends import DistinctCountsSearchQuery
from course_discovery.apps.course_metadata.tests.factories import CourseFactory, CourseRunFactory

class DistinctCountsSearchQuerySetTests(TestCase):
    def test_from_queryset(self):
        """ Verify that a DistinctCountsSearchQuerySet can be built from an existing SearchQuerySet."""
        course_1 = CourseFactory()
        run_1 = CourseRunFactory(title='foo', course=course_1)
        run_2 = CourseRunFactory(title='foo', course=course_1)

        course_2 = CourseFactory()
        run_3 = CourseRunFactory(title='foo', course=course_2)
        run_4 = CourseRunFactory(title='bar', course=course_2)

        queryset = SearchQuerySet().filter(title='foo')
        dc_queryset = DistinctCountsSearchQuerySet.from_queryset(queryset)

        expected = sorted([run.key for run in queryset])
        actual = sorted([run.key for run in dc_queryset])
        assert expected == actual

    def test_with_distinct_counts(self):
        """
        Verify that the query object is converted to a DistinctCountsSearchQuery and the aggregation_key is
        configured properly.
        """
        queryset = SearchQuerySet()
        dc_queryset = DistinctCountsSearchQuerySet.from_queryset(queryset).with_distinct_counts('aggregation_key')
        assert isinstance(dc_queryset.query, DistinctCountsSearchQuery)
        assert dc_queryset.query._aggregation_key == 'aggregation_key'

    def test_distinct_count_returns_cached_distinct_count(self):
        """ Verify that distinct_count returns the cached distinct_result_count when present."""
        queryset = SearchQuerySet()
        dc_queryset = DistinctCountsSearchQuerySet.from_queryset(queryset).with_distinct_counts('aggregation_key')

        dc_queryset._distinct_result_count = 123
        assert dc_queryset.distinct_count() == 123

    def test_distinct_count_runs_query_when_cache_is_empty(self):
        """ Verify that distinct_count runs the query, caches, and returns the distinct_count when cache is empty."""
        course_1 = CourseFactory()
        run_1 = CourseRunFactory(title='foo', course=course_1)
        run_2 = CourseRunFactory(title='foo', course=course_1)

        course_2 = CourseFactory()
        run_3 = CourseRunFactory(title='foo', course=course_2)
        run_4 = CourseRunFactory(title='bar', course=course_2)

        queryset = SearchQuerySet().filter(title='foo')
        dc_queryset = DistinctCountsSearchQuerySet.from_queryset(queryset).with_distinct_counts('aggregation_key')

        assert dc_queryset._distinct_result_count is None
        assert dc_queryset.distinct_count() == 2
        assert dc_queryset._distinct_result_count == 2

    def test_distinct_count_raises_when_not_properly_configured(self):
        """
        Verify that distinct_count raises when called without configuring the SearchQuerySet to compute distinct
        counts.
        """
        queryset = SearchQuerySet()
        dc_queryset = DistinctCountsSearchQuerySet.from_queryset(queryset)

        with pytest.raises(RuntimeError) as err:
            dc_queryset.distinct_count()
        assert str(err.value) == 'This SearchQuerySet has not been configured to compute distinct counts.'

    def test_facet_counts_includes_distinct_counts(self):
        """ Verify that facet_counts include distinct counts. """
        course = CourseFactory()
        run_1 = CourseRunFactory(title='foo', pacing_type='self_paced', hidden=True, course=course)
        run_2 = CourseRunFactory(title='foo', pacing_type='self_paced', hidden=True, course=course)
        run_3 = CourseRunFactory(title='foo', pacing_type='instructor_paced', hidden=False, course=course)

        # Make sure to add both a field facet and a query facet so that we can be sure that both work.
        queryset = SearchQuerySet().filter(title='foo').facet('pacing_type').query_facet('hidden', 'hidden:true')
        dc_queryset = DistinctCountsSearchQuerySet.from_queryset(queryset).with_distinct_counts('aggregation_key')
        facet_counts = dc_queryset.facet_counts()

        # Field facets are expected to be formatted as a list of three-tuples (field_value, count, distinct_count)
        for val, count, distinct_count in facet_counts['fields']['pacing_type']:
            assert val in {'self_paced', 'instructor_paced'}
            if val == 'self_paced':
                assert count == 2
                assert distinct_count == 1
            elif val == 'instructor_paced':
                assert count == 1
                assert distinct_count == 1

        # Query facets are expected to be formatted as a dictionary mapping facet_names to two-tuples (count,
        # distinct_count)
        hidden_count, hidden_distinct_count = facet_counts['queries']['hidden']
        assert hidden_count == 2
        assert hidden_distinct_count == 1
