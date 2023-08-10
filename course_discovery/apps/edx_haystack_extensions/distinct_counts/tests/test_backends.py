import datetime
from unittest import mock

import pytest
from haystack.backends import SQ
from haystack.backends.elasticsearch_backend import ElasticsearchSearchQuery
from haystack.query import SearchQuerySet

from course_discovery.apps.course_metadata.models import CourseRun
from course_discovery.apps.course_metadata.tests.factories import CourseFactory, CourseRunFactory
from course_discovery.apps.edx_haystack_extensions.distinct_counts.backends import (
    DistinctCountsElasticsearchBackendWrapper, DistinctCountsSearchQuery
)


# pylint: disable=protected-access
@pytest.mark.django_db
@pytest.mark.usefixtures('haystack_default_connection')
class TestDistinctCountsSearchQuery:
    def test_clone(self):
        """ Verify that clone copies all fields, including the aggregation_key and distinct_hit_count."""
        query = DistinctCountsSearchQuery()
        query.add_field_facet('pacing_type')
        query.aggregation_key = 'aggregation_key'
        query._distinct_hit_count = 123

        clone = query._clone()
        assert query.facets == clone.facets
        assert query.aggregation_key == clone.aggregation_key
        assert query._distinct_hit_count == clone._distinct_hit_count

    def test_clone_with_different_class(self):
        """ Verify that clone does not copy aggregation_key and distinct_hit_count when using different class."""
        query = DistinctCountsSearchQuery()
        query.add_field_facet('pacing_type')
        query.aggregation_key = 'aggregation_key'
        query._distinct_hit_count = 123

        clone = query._clone(klass=ElasticsearchSearchQuery)
        assert isinstance(clone, ElasticsearchSearchQuery)
        assert query.facets == clone.facets
        assert not hasattr(clone, 'aggregation_key')
        assert not hasattr(clone, '_distinct_hit_count')

    def test_get_distinct_count_returns_cached_value(self):
        """ Verify that get_distinct_count returns the distinct_count from the cache when present."""
        query = DistinctCountsSearchQuery()
        query._distinct_hit_count = 123
        assert query.get_distinct_count() == 123

    def test_get_distinct_count_runs_query_when_cache_empty(self):
        """ Verify that get_distinct_count runs the query and caches/returns the distinct_count."""
        course = CourseFactory()
        CourseRunFactory(title='foo', course=course)
        CourseRunFactory(title='foo', course=course)

        query = DistinctCountsSearchQuery()
        query.aggregation_key = 'aggregation_key'
        query.add_filter(SQ(title='foo'))
        query.add_model(CourseRun)

        assert query._distinct_hit_count is None
        assert query.get_distinct_count() == 1
        assert query._distinct_hit_count == 1

    def test_run_executes_the_query_and_caches_the_results(self):
        """ Verify that run executes the query and caches the results."""
        course_1 = CourseFactory()
        run_1 = CourseRunFactory(title='foo', pacing_type='self_paced', hidden=True, course=course_1)
        run_2 = CourseRunFactory(title='foo', pacing_type='self_paced', hidden=True, course=course_1)

        course_2 = CourseFactory()
        run_3 = CourseRunFactory(title='foo', pacing_type='instructor_paced', hidden=False, course=course_2)
        CourseRunFactory(title='bar', pacing_type='instructor_paced', hidden=False, course=course_2)

        query = DistinctCountsSearchQuery()
        query.aggregation_key = 'aggregation_key'
        query.add_filter(SQ(title='foo'))
        query.add_model(CourseRun)
        query.add_field_facet('pacing_type')
        query.add_query_facet('hidden', 'hidden:true')

        assert query._distinct_hit_count is None
        assert query._hit_count is None
        assert query._results is None
        assert query._facet_counts is None

        query.run()
        expected_results = sorted([run_1.key, run_2.key, run_3.key])
        actual_results = sorted([run.key for run in query._results])
        assert query._distinct_hit_count == 2
        assert query._hit_count == 3
        assert expected_results == actual_results

        facet_counts = query._facet_counts
        for field_val, count, distinct_count in facet_counts['fields']['pacing_type']:
            assert field_val in {'self_paced', 'instructor_paced'}
            if field_val == 'self_paced':
                assert count == 2 and distinct_count == 1
            elif field_val == 'instructor_paced':
                assert count == 1 and distinct_count == 1

        count, distinct_count = facet_counts['queries']['hidden']
        assert count == 2 and distinct_count == 1

    def test_run_handles_pagination(self):
        """ Verify that run supports paginated queries. """
        course_1 = CourseFactory()
        for _ in range(5):
            CourseRunFactory(title='foo', course=course_1)

        query = DistinctCountsSearchQuery()
        query.aggregation_key = 'aggregation_key'
        query.add_filter(SQ(title='foo'))
        query.add_model(CourseRun)

        query.run()
        all_results = query._results
        assert len(all_results) == 5

        query._reset()
        query.set_limits(low=1, high=3)
        query.run()

        paginated_results = query._results
        assert len(paginated_results) == 2

        expected = sorted([run.key for run in all_results[1:3]])
        actual = sorted([run.key for run in paginated_results])
        assert expected == actual

    def test_run_raises_when_validation_fails(self):
        """ Verify that run raises an exception when the Query is misconfigured. """
        with mock.patch.object(DistinctCountsSearchQuery, 'validate') as mock_validate:
            mock_validate.side_effect = RuntimeError('validation failed')
            with pytest.raises(RuntimeError) as err:
                DistinctCountsSearchQuery().run()
            assert str(err.value) == 'validation failed'

    def test_validate_raises_when_configured_with_more_like_this_query(self):
        """ Verify that validate raises when Query configured with more_like_this query."""
        query = DistinctCountsSearchQuery()
        query._more_like_this = True
        with pytest.raises(RuntimeError) as err:
            query.validate()
        assert 'does not support more_like_this queries' in str(err.value)

    def test_validate_raises_when_configured_with_raw_query(self):
        """ Verify that validate raises when Query configured with raw query."""
        # The raw_search method on DistinctCountsSearchQuery raises, so configure a raw query
        # on a normal ElasticsearchSearchQuery and then clone it to a DistinctCountsSearchQuery.
        query = ElasticsearchSearchQuery()
        query.raw_search('title:foo')
        query = query._clone(klass=DistinctCountsSearchQuery)
        query.aggregation_key = 'aggregation_key'

        with pytest.raises(RuntimeError) as err:
            query.validate()
        assert 'does not support raw queries' in str(err.value)

    def test_validate_raises_when_configured_with_date_facet(self):
        """ Verify that validate raises when Query configured with date facet."""
        now = datetime.datetime.now()

        # The add_date_facet method on DistinctCountsSearchQuery raises, so configure a date facet
        # on a normal ElasticsearchSearchQuery and then clone it to a DistinctCountsSearchQuery.
        query = ElasticsearchSearchQuery()
        query.add_date_facet('start', now - datetime.timedelta(days=10), now + datetime.timedelta(days=10), 'day')
        query = query._clone(klass=DistinctCountsSearchQuery)
        query.aggregation_key = 'aggregation_key'

        with pytest.raises(RuntimeError) as err:
            query.validate()
        assert 'does not support date facets' in str(err.value)

    def test_validate_raises_when_configured_with_facet_with_unsupported_options(self):
        """ Verify that validate raises when Query configured with facet with unsupported options."""
        # The add_field_facet method on DistinctCountsSearchQuery raises when unsupported options are passed,
        # so configure a field facet with those options on a normal ElasticsearchSearchQuery and then clone
        # it to a DistinctCountsSearchQuery.
        query = ElasticsearchSearchQuery()
        query.add_field_facet('pacing_type', order='term')
        query = query._clone(klass=DistinctCountsSearchQuery)
        query.aggregation_key = 'aggregation_key'

        with pytest.raises(RuntimeError) as err:
            query.validate()
        assert 'only supports a limited set of field facet options' in str(err.value)

    def test_validate_raises_when_configured_without_aggregation_key(self):
        """ Verify that validate raises when Query configured without aggregation_key."""
        with pytest.raises(RuntimeError) as err:
            DistinctCountsSearchQuery().run()
        assert str(err.value) == 'aggregation_key is required.'

    def test_more_like_this_raises(self):
        """ Verify that more_like_this raises an exception."""
        with pytest.raises(RuntimeError) as err:
            DistinctCountsSearchQuery().more_like_this(None)
        assert 'does not support more_like_this queries' in str(err.value)

    def test_run_mlt_raises(self):
        """ Verify that run_mlt raises an exception."""
        with pytest.raises(RuntimeError) as err:
            DistinctCountsSearchQuery().run_mlt()
        assert 'does not support more_like_this queries' in str(err.value)

    def test_raw_search_raises(self):
        """ Verify that raw_search raises an exception."""
        with pytest.raises(RuntimeError) as err:
            DistinctCountsSearchQuery().raw_search(None)
        assert 'does not support raw queries' in str(err.value)

    def test_run_raw_raises(self):
        """ Verify that run_raw raises an exception."""
        with pytest.raises(RuntimeError) as err:
            DistinctCountsSearchQuery().run_raw()
        assert 'does not support raw queries' in str(err.value)

    def test_add_date_facet_raises(self):
        """ Verify that add_date_facet raises an exception. """
        with pytest.raises(RuntimeError) as err:
            DistinctCountsSearchQuery().add_date_facet(None, None, None, None)
        assert 'does not support date facets' in str(err.value)

    def test_add_field_facet_validates_options(self):
        """ Verify that add_field_facet validates the provided options."""
        query = DistinctCountsSearchQuery()
        with pytest.raises(RuntimeError) as err:
            query.add_field_facet('pacing_type', order='term')
        assert 'only supports a limited set of field facet options' in str(err.value)

        query.add_field_facet('pacing_type', size=5)
        assert query.facets['pacing_type_exact']['size'] == 5


@pytest.mark.django_db
@pytest.mark.usefixtures('haystack_default_connection')
class TestDistinctCountsElasticsearchBackendWrapper:
    def test_search_raises_when_called_with_date_facet(self):
        now = datetime.datetime.now()
        one_day = datetime.timedelta(days=1)

        queryset = SearchQuerySet().date_facet('start', now - one_day, now + one_day, 'day')
        querystring = queryset.query.build_query()
        params = queryset.query.build_params()
        backend = DistinctCountsElasticsearchBackendWrapper(queryset.query.backend, 'aggregation_key')

        with pytest.raises(RuntimeError) as err:
            backend.search(querystring, **params)
        assert 'does not support date facets' in str(err.value)

    def test_search_raises_when_called_with_unsupported_field_facet_option(self):
        queryset = SearchQuerySet().facet('pacing_type', order='term')
        querystring = queryset.query.build_query()
        params = queryset.query.build_params()
        backend = DistinctCountsElasticsearchBackendWrapper(queryset.query.backend, 'aggregation_key')

        with pytest.raises(RuntimeError) as err:
            backend.search(querystring, **params)
        assert 'field facet with unsupported options' in str(err.value)

    def test_build_search_kwargs_does_not_include_facet_clause(self):
        """ Verify that a facets clause is not included with search kwargs."""
        queryset = SearchQuerySet().query_facet('hidden', 'hidden:true').facet('pacing_type')
        querystring = queryset.query.build_query()
        params = queryset.query.build_params()
        backend = DistinctCountsElasticsearchBackendWrapper(queryset.query.backend, 'aggregation_key')

        search_kwargs = backend._build_search_kwargs(querystring, **params)
        assert 'facets' not in search_kwargs
        assert 'aggregations' in search_kwargs
