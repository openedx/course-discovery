import datetime
from unittest import mock

import pytest
from haystack.query import SearchQuerySet

from course_discovery.apps.course_metadata.models import CourseRun
from course_discovery.apps.course_metadata.tests.factories import CourseFactory, CourseRunFactory
from course_discovery.apps.edx_haystack_extensions.distinct_counts.backends import DistinctCountsSearchQuery
from course_discovery.apps.edx_haystack_extensions.distinct_counts.query import DistinctCountsSearchQuerySet


@pytest.mark.django_db
@pytest.mark.usefixtures('haystack_default_connection')
class TestDistinctCountsSearchQuerySet:
    def test_from_queryset(self):
        """ Verify that a DistinctCountsSearchQuerySet can be built from an existing SearchQuerySet."""
        course_1 = CourseFactory()
        CourseRunFactory(title='foo', course=course_1)
        CourseRunFactory(title='foo', course=course_1)

        course_2 = CourseFactory()
        CourseRunFactory(title='foo', course=course_2)
        CourseRunFactory(title='bar', course=course_2)

        queryset = SearchQuerySet().filter(title='foo').models(CourseRun)
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
        assert dc_queryset.query.aggregation_key == 'aggregation_key'

    def test_with_distinct_counts_raises_when_queryset_includes_unsupported_options(self):
        """
        Verify that an error is raised if the original queryset includes options that are not supported by our
        custom Query class.
        """
        dc_queryset = DistinctCountsSearchQuerySet.from_queryset(SearchQuerySet())

        with pytest.raises(RuntimeError) as err:
            now = datetime.datetime.now()
            ten_days = datetime.timedelta(days=10)
            start = now - ten_days
            end = now + ten_days
            dc_queryset.date_facet('start', start, end, 'day').with_distinct_counts('aggregation_key')
        assert str(err.value) == 'DistinctCountsSearchQuery does not support date facets.'

        with pytest.raises(RuntimeError) as err:
            dc_queryset.facet('pacing_type', order='term').with_distinct_counts('aggregation_key')
        assert 'DistinctCountsSearchQuery only supports a limited set of field facet options.' in str(err.value)

    def test_distinct_count_returns_cached_distinct_count(self):
        """ Verify that distinct_count returns the cached distinct_result_count when present."""
        queryset = SearchQuerySet()
        dc_queryset = DistinctCountsSearchQuerySet.from_queryset(queryset).with_distinct_counts('aggregation_key')

        dc_queryset._distinct_result_count = 123  # pylint: disable=protected-access
        assert dc_queryset.distinct_count() == 123

    def test_distinct_count_runs_query_when_cache_is_empty(self):
        """ Verify that distinct_count runs the query, caches, and returns the distinct_count when cache is empty."""
        course_1 = CourseFactory()
        CourseRunFactory(title='foo', course=course_1)
        CourseRunFactory(title='foo', course=course_1)

        course_2 = CourseFactory()
        CourseRunFactory(title='foo', course=course_2)
        CourseRunFactory(title='bar', course=course_2)

        queryset = SearchQuerySet().filter(title='foo').models(CourseRun)
        dc_queryset = DistinctCountsSearchQuerySet.from_queryset(queryset).with_distinct_counts('aggregation_key')

        assert dc_queryset._distinct_result_count is None  # pylint: disable=protected-access
        assert dc_queryset.distinct_count() == 2
        assert dc_queryset._distinct_result_count == 2  # pylint: disable=protected-access

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
        CourseRunFactory(title='foo', pacing_type='self_paced', hidden=True, course=course)
        CourseRunFactory(title='foo', pacing_type='self_paced', hidden=True, course=course)
        CourseRunFactory(title='foo', pacing_type='instructor_paced', hidden=False, course=course)

        # Make sure to add both a field facet and a query facet so that we can be sure that both work.
        queryset = SearchQuerySet().filter(title='foo').models(CourseRun)
        queryset = queryset.facet('pacing_type').query_facet('hidden', 'hidden:true')
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

    def test_facet_counts_caches_results(self):
        """ Verify that facet_counts cache results when it is forced to run the query."""
        course = CourseFactory()
        runs = [
            CourseRunFactory(title='foo', pacing_type='self_paced', hidden=True, course=course),
            CourseRunFactory(title='foo', pacing_type='self_paced', hidden=True, course=course),
            CourseRunFactory(title='foo', pacing_type='instructor_paced', hidden=False, course=course),
        ]

        queryset = SearchQuerySet().filter(title='foo').models(CourseRun)
        queryset = queryset.facet('pacing_type').query_facet('hidden', 'hidden:true')
        dc_queryset = DistinctCountsSearchQuerySet.from_queryset(queryset).with_distinct_counts('aggregation_key')

        # This should force the query to run and the results to be cached
        facet_counts = dc_queryset.facet_counts()

        with mock.patch.object(DistinctCountsSearchQuery, 'run') as mock_run:
            # Calling facet_counts again shouldn't result in an additional query
            cached_facet_counts = dc_queryset.facet_counts()
            assert not mock_run.called
            assert facet_counts == cached_facet_counts

            # Calling count shouldn't result in another query, as we should have already cached it with the
            # first request.
            count = dc_queryset.count()
            assert not mock_run.called
            assert count == len(runs)

            # Fetching the results shouldn't result in another query, as we should have already cached them
            # with the initial request.
            results = dc_queryset[:]
            assert not mock_run.called
            expected = {run.key for run in runs}
            actual = {run.key for run in results}
            assert expected == actual
