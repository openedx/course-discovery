import copy

from django.core.exceptions import ImproperlyConfigured
from django_elasticsearch_dsl_drf.constants import MATCHING_OPTION_MUST, MATCHING_OPTIONS
from django_elasticsearch_dsl_drf.filter_backends import FacetedSearchFilterBackend, FilteringFilterBackend
from django_elasticsearch_dsl_drf.filter_backends.mixins import FilterBackendMixin
from django_elasticsearch_dsl_drf.filter_backends.search import BaseSearchFilterBackend as OriginBaseSearchFilterBackend
from django_elasticsearch_dsl_drf.filter_backends.search.query_backends import \
    MultiMatchQueryBackend as OriginMultiMatchQueryBackend
from elasticsearch_dsl.query import Q as ESDSLQ
from rest_framework.exceptions import ParseError
from rest_framework.filters import BaseFilterBackend

from course_discovery.apps.edx_elasticsearch_dsl_extensions.constants import SEPARATOR_LOOKUP_NAME
from course_discovery.apps.edx_elasticsearch_dsl_extensions.elasticsearch_boost_config import (
    get_elasticsearch_boost_config
)
from course_discovery.apps.edx_elasticsearch_dsl_extensions.mixins import (
    CatalogDataFilterBackendMixin, FieldActionFilterBackendMinix, MatchFilterBackendMixin
)


# pylint: disable=abstract-method
class BaseSearchFilterBackend(OriginBaseSearchFilterBackend):

    @classmethod
    def split_lookup_name(cls, value, maxsplit=-1):
        """
        Split lookup value.
        """
        return value.split(SEPARATOR_LOOKUP_NAME, maxsplit)

    def filter_queryset(self, request, queryset, view):
        function_score_config = get_elasticsearch_boost_config()['function_score']
        if self.matching not in MATCHING_OPTIONS:
            raise ImproperlyConfigured(
                'Your `matching` value does not match the allowed matching\t'
                'options: {}'.format(', '.join(MATCHING_OPTIONS))
            )

        __query_backends = self._get_query_backends(request, view)

        if len(__query_backends) > 1:
            __queries = []
            for query_backend in __query_backends:
                __queries.extend(query_backend.construct_search(request=request, view=view, search_backend=self))

            if __queries:
                function_score_config['query'] = {self.matching: __queries}

        elif len(__query_backends) == 1:
            __query = __query_backends[0].construct_search(request=request, view=view, search_backend=self)
            function_score_config['query'] = {'bool': {self.matching: __query}}
        else:
            raise ImproperlyConfigured(
                'Search filter backend shall have at least one query_backend\t'
                'specified either in `query_backends` property or\t'
                '`get_query_backends` method. Make appropriate changes to\t'
                'your {} class'.format(self.__class__.__name__)
            )
        queryset = queryset.query('function_score', **function_score_config)

        return queryset


class MultiMatchSearchFilterBackend(BaseSearchFilterBackend):
    """
    Multi match search filter backend.
    """

    search_param = 'q'
    matching = MATCHING_OPTION_MUST

    query_backends = [OriginMultiMatchQueryBackend]

    def get_search_query_params(self, request):
        """
        Get search query params.

        :param request: Django REST framework request.
        :type request: rest_framework.request.Request
        :return: List of search query params.
        :rtype: list
        """
        query_params = request.query_params.copy()
        for param in request.query_params:
            if not query_params[param]:
                query_params.pop(param)
        return query_params.getlist(self.search_param, [])


class FacetedFieldSearchFilterBackend(FacetedSearchFilterBackend):
    faceted_filter_param = 'selected_facets'

    def get_faceted_filter_params(self, request):
        """
        Get faceted search query params.

        :param request: Django REST framework request.
        :type request: rest_framework.request.Request
        :return: List of search query params.
        :rtype: list
        """
        query_params = request.query_params.copy()
        return query_params.getlist(self.faceted_filter_param, [])

    def prepare_faceted_field_filter_params(self, request):
        filter_params = self.get_faceted_filter_params(request)
        for param in filter_params:
            field, __, value = param.partition(':')
            if field.endswith('_exact'):
                field, *_ = field.partition('_exact')

            yield field, value

    def filter_by_facets(self, request, queryset, view):
        filter_params = self.prepare_faceted_field_filter_params(request)
        _filters = []
        field_facets = view.faceted_search_fields
        for field, value in filter_params:
            if not field_facets.get(field):
                raise ParseError('The selected query facet [{facet}] is not valid.'.format(facet=field))

            _filters.append(ESDSLQ('term', **{field: value}))

        queryset = queryset.query('bool', **{'filter': _filters})
        return queryset

    def filter_queryset(self, request, queryset, view):
        queryset = self.filter_by_facets(request, queryset, view)
        return self.aggregate(request, queryset, view)


class FacetedQueryFilterBackend(BaseFilterBackend, FilterBackendMixin):
    """
    Facet query filter backend.

    Adds query facets.
    """

    faceted_filter_param = 'selected_query_facets'

    def get_faceted_filter_params(self, request):
        """
        Get faceted search query params.

        :param request: Django REST framework request.
        :type request: rest_framework.request.Request
        :return: List of search query params.
        :rtype: list
        """
        query_params = request.query_params.copy()
        return query_params.getlist(self.faceted_filter_param, [])

    @staticmethod
    def prepare_faceted_query_search_fields(view):
        faceted_query_filter_fields = copy.deepcopy(view.faceted_query_filter_fields)
        for name in faceted_query_filter_fields:
            if 'enabled' not in faceted_query_filter_fields[name]:
                faceted_query_filter_fields[name]['enabled'] = False
            if not faceted_query_filter_fields[name].get('query'):
                faceted_query_filter_fields[name]['query'] = []

        return faceted_query_filter_fields

    def construct_query_filter_facets(self, request, view):
        facets = {}
        faceted_query_search_fields = self.prepare_faceted_query_search_fields(view)
        for name, options in faceted_query_search_fields.items():
            if options['enabled']:
                facets[name] = ESDSLQ('bool', filter=options['query'])
        return facets

    def aggregate(self, request, queryset, view):
        facets = self.construct_query_filter_facets(request, view)
        for name, query_filter in facets.items():
            queryset.aggs.bucket('_query_{0}'.format(name), 'filter', filter=query_filter)

        return queryset

    def filter_by_facets(self, request, queryset, view):
        filter_params = self.get_faceted_filter_params(request)
        _queries = []
        facets = self.construct_query_filter_facets(request, view)
        for parm in filter_params:
            query_filter = facets.get(parm)
            if not query_filter:
                raise ParseError('The selected query facet [{facet}] is not valid.'.format(facet=parm))
            _queries.append(query_filter)

        queryset = queryset.query('bool', **{'filter': _queries})
        return queryset

    def filter_queryset(self, request, queryset, view):
        queryset = self.filter_by_facets(request, queryset, view)
        return self.aggregate(request, queryset, view)


class CatalogDataFilterBackend(
    CatalogDataFilterBackendMixin,
    FieldActionFilterBackendMinix,
    MatchFilterBackendMixin,
    FilteringFilterBackend
):
    """
    Catalog data filter backend
    """


class AggregateDataFilterBackend(FieldActionFilterBackendMinix, MatchFilterBackendMixin, FilteringFilterBackend):
    """
    Aggregate data filter backend
    """
