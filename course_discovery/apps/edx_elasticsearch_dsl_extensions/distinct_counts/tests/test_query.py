from unittest import mock

import pytest
from elasticsearch_dsl import DateHistogramFacet, Search, TermsFacet
from elasticsearch_dsl.query import Q as ESDSLQ

from course_discovery.apps.course_metadata.search_indexes.documents import CourseRunDocument
from course_discovery.apps.course_metadata.tests.factories import CourseFactory, CourseRunFactory
from course_discovery.apps.edx_elasticsearch_dsl_extensions.distinct_counts.query import (
    DistinctCountsElasticsearchQueryWrapper, DistinctCountsSearchQuerySet
)
from course_discovery.apps.edx_elasticsearch_dsl_extensions.search import FacetedSearch as DSLFacetedSearch
from course_discovery.apps.edx_elasticsearch_dsl_extensions.viewsets import FacetedSearch

# pylint: disable=protected-access


@pytest.mark.django_db
@pytest.mark.usefixtures('elasticsearch_dsl_default_connection')
class TestDistinctCountsSearchQuerySet:
    def test_from_queryset(self):
        """ Verify that a DistinctCountsSearchQuerySet can be built from an existing SearchQuerySet."""
        course_1 = CourseFactory()
        CourseRunFactory(title='foo', course=course_1)
        CourseRunFactory(title='foo', course=course_1)

        course_2 = CourseFactory()
        CourseRunFactory(title='foo', course=course_2)
        CourseRunFactory(title='bar', course=course_2)
        queryset = DSLFacetedSearch(index=CourseRunDocument._index._name).filter('term', title='foo')
        dc_queryset = DistinctCountsSearchQuerySet.from_queryset(queryset)

        expected = sorted([run.key for run in queryset])
        actual = sorted([run.key for run in dc_queryset])
        assert expected == actual

    def test_with_distinct_counts(self):
        """
        Verify that the query object is converted to a DistinctCountsSearchQuerySet and the aggregation_key is
        configured properly.
        """
        queryset = DSLFacetedSearch()
        dc_queryset = DistinctCountsSearchQuerySet.from_queryset(queryset).with_distinct_counts('aggregation_key')
        assert isinstance(dc_queryset, DistinctCountsSearchQuerySet)
        assert dc_queryset.aggregation_key == 'aggregation_key'

    def test_with_distinct_counts_raises_when_queryset_includes_unsupported_options(self):
        """
        Verify that an error is raised if the original queryset includes options that are not supported by our
        custom Search class.
        """
        dc_queryset = DistinctCountsSearchQuerySet.from_queryset(DSLFacetedSearch())
        with pytest.raises(RuntimeError) as err:
            facet_field = 'start'
            agg_filter = ESDSLQ('match_all')
            agg = DateHistogramFacet(field=facet_field, interval='month')
            dc_queryset.aggs.bucket('_filter_' + facet_field, 'filter', filter=agg_filter).bucket(
                facet_field, agg.get_aggregation()
            )
            dc_queryset.with_distinct_counts('aggregation_key')
        assert str(err.value) == 'DistinctCountsSearchQuerySet does not support date facets.'

        dc_queryset = DistinctCountsSearchQuerySet.from_queryset(DSLFacetedSearch())
        with pytest.raises(RuntimeError) as err:
            facet_field = 'pacing_type'
            agg_filter = ESDSLQ('match_all')
            agg = TermsFacet(field=facet_field, order='term')
            dc_queryset.aggs.bucket('_filter_' + facet_field, 'filter', filter=agg_filter).bucket(
                facet_field, agg.get_aggregation()
            )
            dc_queryset.with_distinct_counts('aggregation_key')
        assert 'DistinctCountsSearchQuerySet only supports a limited set of field facet options.' in str(err.value)

    def test_distinct_count_returns_cached_distinct_count(self):
        """ Verify that distinct_count returns the cached distinct_result_count when present."""
        queryset = DSLFacetedSearch()
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

        queryset = DSLFacetedSearch(index=CourseRunDocument._index._name).filter('term', title='foo')
        dc_queryset = DistinctCountsSearchQuerySet.from_queryset(queryset).with_distinct_counts('aggregation_key')

        assert dc_queryset._distinct_result_count is None  # pylint: disable=protected-access
        assert dc_queryset.distinct_count() == 2
        assert dc_queryset._distinct_result_count == 2  # pylint: disable=protected-access

    def test_distinct_count_raises_when_not_properly_configured(self):
        """
        Verify that distinct_count raises when called without configuring the DSLFacetedSearch to compute distinct
        counts.
        """
        queryset = DSLFacetedSearch()
        dc_queryset = DistinctCountsSearchQuerySet.from_queryset(queryset)

        with pytest.raises(AttributeError) as err:
            dc_queryset.distinct_count()
        assert "object has no attribute 'distinct_count'" in str(err.value)

    def test_facet_counts_includes_distinct_counts(self):
        """ Verify that facet_counts include distinct counts. """
        course = CourseFactory()
        CourseRunFactory(title='foo', pacing_type='self_paced', hidden=True, course=course)
        CourseRunFactory(title='foo', pacing_type='self_paced', hidden=True, course=course)
        CourseRunFactory(title='foo', pacing_type='instructor_paced', hidden=False, course=course)

        # Make sure to add both a field facet and a query facet so that we can be sure that both work.
        queryset = DSLFacetedSearch(index=CourseRunDocument._index._name).filter('term', title='foo')
        facet_field = 'pacing_type'
        agg_filter = ESDSLQ('match_all')
        agg = TermsFacet(field=facet_field)
        queryset.aggs.bucket('_filter_' + facet_field, 'filter', filter=agg_filter).bucket(
            facet_field, agg.get_aggregation()
        )
        queryset.aggs.bucket(
            '_query_{0}'.format('hidden'), 'filter', filter=ESDSLQ('bool', filter=ESDSLQ('term', hidden=True))
        )
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

        queryset = DSLFacetedSearch(index=CourseRunDocument._index._name).filter('term', title='foo')
        facet_field = 'pacing_type'
        agg_filter = ESDSLQ('match_all')
        agg = TermsFacet(field=facet_field)
        queryset.aggs.bucket('_filter_' + facet_field, 'filter', filter=agg_filter).bucket(
            facet_field, agg.get_aggregation()
        )
        queryset.aggs.bucket(
            '_query_{0}'.format('hidden'), 'filter', filter=ESDSLQ('bool', filter=ESDSLQ('term', hidden=True))
        )
        dc_queryset = DistinctCountsSearchQuerySet.from_queryset(queryset).with_distinct_counts('aggregation_key')
        # This should force the query to execute, and the results to be cached
        facet_counts = dc_queryset.facet_counts()

        with mock.patch.object(DistinctCountsElasticsearchQueryWrapper, 'search') as mock_search:
            # Calling facet_counts again shouldn't result in an additional query
            cached_facet_counts = dc_queryset.facet_counts()
            assert not mock_search.called
            assert facet_counts == cached_facet_counts

            # Calling count shouldn't result in another query, as we should have already cached it with the
            # first request.
            count = dc_queryset.count()
            assert not mock_search.called
            assert count == len(runs)

            # Fetching the results shouldn't result in another query, as we should have already cached them
            # with the initial request.
            results = dc_queryset.execute()
            assert not mock_search.called
            expected = {run.key for run in runs}
            actual = {run.key for run in results}
            assert expected == actual


@pytest.mark.django_db
@pytest.mark.usefixtures('elasticsearch_dsl_default_connection')
class TestDistinctCountsSearchQuery:
    def test_clone(self):
        """ Verify that clone copies all fields, including the aggregation_key and distinct_hit_count."""
        queryset = DistinctCountsSearchQuerySet()
        facet_field = 'pacing_type'
        agg_filter = ESDSLQ('match_all')
        agg = TermsFacet(field=facet_field)
        queryset.aggs.bucket('_filter_' + facet_field, 'filter', filter=agg_filter).bucket(
            facet_field, agg.get_aggregation()
        )

        queryset.aggregation_key = 'aggregation_key'
        queryset._distinct_result_count = 123

        clone = queryset._clone()
        assert queryset.to_dict() == clone.to_dict()
        assert queryset.aggregation_key == clone.aggregation_key
        assert queryset._distinct_result_count == clone._distinct_result_count

    def test_clone_with_different_class(self):
        """ Verify that clone does not copy aggregation_key and distinct_result_count when using different class."""
        queryset = DistinctCountsSearchQuerySet()
        facet_field = 'pacing_type'
        agg_filter = ESDSLQ('match_all')
        agg = TermsFacet(field=facet_field)
        queryset.aggs.bucket('_filter_' + facet_field, 'filter', filter=agg_filter).bucket(
            facet_field, agg.get_aggregation()
        )
        queryset.aggregation_key = 'aggregation_key'
        queryset._distinct_result_count = 123

        clone = queryset._clone(klass=Search)
        assert isinstance(clone, Search)
        assert queryset.to_dict() == clone.to_dict()
        assert not hasattr(clone, 'aggregation_key')
        assert not hasattr(clone, '_distinct_result_count')

    def test_get_distinct_count_returns_cached_value(self):
        """ Verify that the distinct_count from the cache when present."""
        query = DistinctCountsSearchQuerySet()
        query._distinct_result_count = 123
        assert query.distinct_count() == 123

    def test_get_distinct_count_runs_query_when_cache_empty(self):
        """ Verify that distinct_count runs the query and caches/returns the distinct_count."""
        course = CourseFactory()
        CourseRunFactory(title='foo', course=course)
        CourseRunFactory(title='foo', course=course)
        queryset = DistinctCountsSearchQuerySet(index=CourseRunDocument._index._name).filter('term', title='foo')
        queryset.aggregation_key = 'aggregation_key'

        assert queryset._distinct_result_count is None
        assert queryset.distinct_count() == 1
        assert queryset._distinct_result_count == 1

    def test_run_executes_the_query_and_caches_the_results(self):
        """ Verify that run executes the query and caches the results."""
        course_1 = CourseFactory()
        run_1 = CourseRunFactory(title='foo', pacing_type='self_paced', hidden=True, course=course_1)
        run_2 = CourseRunFactory(title='foo', pacing_type='self_paced', hidden=True, course=course_1)

        course_2 = CourseFactory()
        run_3 = CourseRunFactory(title='foo', pacing_type='instructor_paced', hidden=False, course=course_2)
        CourseRunFactory(title='bar', pacing_type='instructor_paced', hidden=False, course=course_2)

        queryset = DistinctCountsSearchQuerySet(index=CourseRunDocument._index._name).filter('term', title='foo')
        queryset.aggregation_key = 'aggregation_key'
        facet_field = 'pacing_type'
        agg_filter = ESDSLQ('match_all')
        agg = TermsFacet(field=facet_field)
        queryset.aggs.bucket('_filter_' + facet_field, 'filter', filter=agg_filter).bucket(
            facet_field, agg.get_aggregation()
        )

        queryset.aggs.bucket(
            '_query_{0}'.format('hidden'), 'filter', filter=ESDSLQ('bool', filter=ESDSLQ('term', hidden=True))
        )

        assert queryset._distinct_result_count is None
        assert not hasattr(self, '_response')

        queryset.execute()
        expected_results = sorted([run_1.key, run_2.key, run_3.key])
        actual_results = sorted([run.key for run in queryset._response.hits])
        assert queryset._distinct_result_count == 2
        assert queryset._response.hits.total['value'] == 3
        assert expected_results == actual_results
        facet_counts = queryset._response.facets
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

        queryset = DistinctCountsSearchQuerySet(index=CourseRunDocument._index._name).filter('term', title='foo')
        queryset.aggregation_key = 'aggregation_key'

        queryset.execute()
        all_results = queryset._response.hits
        assert len(all_results) == 5
        del queryset._response
        queryset = queryset.query().extra(from_=1, size=2)
        queryset.execute()
        paginated_results = queryset._response.hits
        assert len(paginated_results) == 2

        expected = sorted([run.key for run in all_results[1:3]])
        actual = sorted([run.key for run in paginated_results])
        assert expected == actual

    def test_run_raises_when_validation_fails(self):
        """ Verify that run raises an exception when the Search is misconfigured. """
        with mock.patch.object(DistinctCountsSearchQuerySet, 'validate') as mock_validate:
            mock_validate.side_effect = RuntimeError('validation failed')
            with pytest.raises(RuntimeError) as err:
                DistinctCountsSearchQuerySet().execute()
            assert str(err.value) == 'validation failed'

    def test_validate_raises_when_configured_with_date_facet(self):
        """ Verify that validate raises when Query configured with date facet."""

        # The add date facet action on DistinctCountsSearchQuerySet raises, so configure a date facet
        # on a normal FacetedSearch or Search and then clone it to a DistinctCountsSearchQuerySet.
        queryset = FacetedSearch(index=CourseRunDocument._index._name)
        facet_field = 'start'
        agg_filter = ESDSLQ('match_all')
        agg = DateHistogramFacet(field=facet_field, interval='month')
        queryset.aggs.bucket('_filter_' + facet_field, 'filter', filter=agg_filter).bucket(
            facet_field, agg.get_aggregation()
        )

        queryset = queryset._clone(klass=DistinctCountsSearchQuerySet)
        queryset.aggregation_key = 'aggregation_key'

        with pytest.raises(RuntimeError) as err:
            queryset.validate()
        assert 'does not support date facets' in str(err.value)

    def test_validate_raises_when_configured_with_facet_with_unsupported_options(self):
        """ Verify that validate raises when Query configured with facet with unsupported options."""
        # The add date facet action on DistinctCountsSearchQuerySet raises when unsupported options are passed,
        # so configure a field facet with those options on a normal FacetedSearch or Search and then clone
        # it to a DistinctCountsSearchQuery.
        queryset = DistinctCountsSearchQuerySet(index=CourseRunDocument._index._name)
        facet_field = 'pacing_type'
        agg_filter = ESDSLQ('match_all')
        agg = TermsFacet(field=facet_field, order='term')
        queryset.aggs.bucket('_filter_' + facet_field, 'filter', filter=agg_filter).bucket(
            facet_field, agg.get_aggregation()
        )
        queryset = queryset._clone(klass=DistinctCountsSearchQuerySet)
        queryset.aggregation_key = 'aggregation_key'

        with pytest.raises(RuntimeError) as err:
            queryset.validate()
        assert 'only supports a limited set of field facet options' in str(err.value)

    def test_validate_raises_when_configured_without_aggregation_key(self):
        """ Verify that validate raises when DistinctCountsSearchQuerySet configured without aggregation_key."""
        with pytest.raises(RuntimeError) as err:
            DistinctCountsSearchQuerySet().execute()
        assert str(err.value) == 'aggregation_key is required.'

    def test_from_dict_search_raises(self):
        """ Verify that from_dict raises an exception."""
        with pytest.raises(RuntimeError) as err:
            DistinctCountsSearchQuerySet.from_dict({})
        assert 'does not support raw queries' in str(err.value)

    def test_update_from_dict_search_raises(self):
        """ Verify that update_from_dict raises an exception."""
        with pytest.raises(RuntimeError) as err:
            DistinctCountsSearchQuerySet().update_from_dict()
        assert 'does not support raw queries' in str(err.value)


@pytest.mark.django_db
@pytest.mark.usefixtures('elasticsearch_dsl_default_connection')
class TestDistinctCountsElasticsearchQueryWrapper:
    def test_search_raises_when_called_with_date_facet(self):
        queryset = DistinctCountsSearchQuerySet(index=CourseRunDocument._index._name)
        facet_field = 'start'
        agg_filter = ESDSLQ('match_all')
        agg = DateHistogramFacet(field=facet_field, interval='month')
        queryset.aggs.bucket('_filter_' + facet_field, 'filter', filter=agg_filter).bucket(
            facet_field, agg.get_aggregation()
        )
        backend = DistinctCountsElasticsearchQueryWrapper(queryset, 'aggregation_key')

        querystring = queryset.to_dict()
        with pytest.raises(RuntimeError) as err:
            backend.search(querystring)
        assert 'does not support date facets' in str(err.value)

    def test_search_raises_when_called_with_unsupported_field_facet_option(self):
        queryset = DistinctCountsSearchQuerySet(index=CourseRunDocument._index._name)
        facet_field = 'pacing_type'
        agg_filter = ESDSLQ('match_all')
        agg = TermsFacet(field=facet_field, order='term')
        queryset.aggs.bucket('_filter_' + facet_field, 'filter', filter=agg_filter).bucket(
            facet_field, agg.get_aggregation()
        )
        backend = DistinctCountsElasticsearchQueryWrapper(queryset, 'aggregation_key')

        querystring = queryset.to_dict()
        with pytest.raises(RuntimeError) as err:
            backend.search(querystring)
        assert 'only supports a limited set of field facet options' in str(err.value)

    def test_build_search_kwargs_does_not_include_facet_clause(self):
        """ Verify that a facets clause is not included with search kwargs."""
        queryset = DistinctCountsSearchQuerySet(index=CourseRunDocument._index._name)
        facet_field = 'pacing_type'
        agg_filter = ESDSLQ('match_all')
        agg = TermsFacet(field=facet_field)
        queryset.aggs.bucket('_filter_' + facet_field, 'filter', filter=agg_filter).bucket(
            facet_field, agg.get_aggregation()
        )

        queryset.aggs.bucket(
            '_query_{0}'.format('hidden'), 'filter', filter=ESDSLQ('bool', filter=ESDSLQ('term', hidden=True))
        )
        querystring_params = queryset.to_dict()
        backend = DistinctCountsElasticsearchQueryWrapper(queryset, 'aggregation_key')
        search_kwargs = backend._build_search_kwargs(**querystring_params)

        assert 'facets' not in search_kwargs
        assert 'aggs' in search_kwargs
