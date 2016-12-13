from drf_haystack.mixins import FacetMixin
from drf_haystack.viewsets import HaystackViewSet
from haystack.backends import SQ
from haystack.inputs import AutoQuery
from haystack.query import SearchQuerySet
from rest_framework import status
from rest_framework.decorators import list_route
from rest_framework.exceptions import ParseError
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from course_discovery.apps.api import filters, serializers
from course_discovery.apps.api.pagination import PageNumberPagination
from course_discovery.apps.course_metadata.choices import ProgramStatus
from course_discovery.apps.course_metadata.models import Course, CourseRun, Program


class BaseHaystackViewSet(FacetMixin, HaystackViewSet):
    document_uid_field = 'key'
    facet_filter_backends = [filters.HaystackFacetFilterWithQueries, filters.HaystackFilter, OrderingFilter]
    ordering_fields = ('start',)

    load_all = True
    lookup_field = 'key'
    permission_classes = (IsAuthenticated,)

    # NOTE: We use PageNumberPagination because drf-haystack's facet serializer relies on the page_query_param
    # attribute, and it is more appropriate for search results than our default limit-offset pagination.
    pagination_class = PageNumberPagination

    def list(self, request, *args, **kwargs):
        """
        Search.
        ---
        parameters:
            - name: q
              description: Search text
              paramType: query
              type: string
              required: false
        """
        return super(BaseHaystackViewSet, self).list(request, *args, **kwargs)

    @list_route(methods=['get'], url_path='facets')
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
        return super(BaseHaystackViewSet, self).facets(request)

    def filter_facet_queryset(self, queryset):
        queryset = super().filter_facet_queryset(queryset)

        q = self.request.query_params.get('q')
        if q:
            queryset = queryset.filter(SQ(text=AutoQuery(q)) | SQ(title=AutoQuery(q)))

        facet_serializer_cls = self.get_facet_serializer_class()
        field_queries = getattr(facet_serializer_cls.Meta, 'field_queries', {})

        # Ensure we only return published, non-hidden items
        queryset = queryset.filter(published=True).exclude(hidden=True)

        for facet in self.request.query_params.getlist('selected_query_facets'):
            query = field_queries.get(facet)

            if not query:
                raise ParseError('The selected query facet [{facet}] is not valid.'.format(facet=facet))

            queryset = queryset.raw_search(query['query'])

        return queryset


class CourseSearchViewSet(BaseHaystackViewSet):
    facet_serializer_class = serializers.CourseFacetSerializer
    index_models = (Course,)
    serializer_class = serializers.CourseSearchSerializer


class CourseRunSearchViewSet(BaseHaystackViewSet):
    facet_serializer_class = serializers.CourseRunFacetSerializer
    index_models = (CourseRun,)
    serializer_class = serializers.CourseRunSearchSerializer


class ProgramSearchViewSet(BaseHaystackViewSet):
    document_uid_field = 'uuid'
    lookup_field = 'uuid'
    facet_serializer_class = serializers.ProgramFacetSerializer
    index_models = (Program,)
    serializer_class = serializers.ProgramSearchSerializer


class AggregateSearchViewSet(BaseHaystackViewSet):
    """ Search all content types. """
    facet_serializer_class = serializers.AggregateFacetSearchSerializer
    serializer_class = serializers.AggregateSearchSerializer


class TypeaheadSearchView(APIView):
    """ Typeahead for courses and programs. """
    RESULT_COUNT = 3
    permission_classes = (IsAuthenticated,)

    def get_results(self, query):
        sqs = SearchQuerySet()
        clean_query = sqs.query.clean(query)

        course_runs = sqs.models(CourseRun).filter(
            SQ(title_autocomplete=clean_query) |
            SQ(course_key=clean_query) |
            SQ(authoring_organizations_autocomplete=clean_query)
        )
        course_runs = course_runs.filter(published=True).exclude(hidden=True)
        course_runs = course_runs[:self.RESULT_COUNT]

        programs = sqs.models(Program).filter(
            SQ(title_autocomplete=clean_query) |
            SQ(authoring_organizations_autocomplete=clean_query)
        )
        programs = programs.filter(status=ProgramStatus.Active)
        programs = programs[:self.RESULT_COUNT]

        return course_runs, programs

    def get(self, request, *args, **kwargs):
        """
        Typeahead uses the ngram_analyzer as the index_analyzer to generate ngrams of the title during indexing.
        i.e. Data Science -> da, dat, at, ata, data, etc...
        Typeahead uses the lowercase analyzer as the search_analyzer.
        The ngram_analyzer uses the lowercase filter as well, which makes typeahead case insensitive.
        Available analyzers are defined in index _settings and field level analyzers are defined in the index _mapping.
        NGrams are used rather than EdgeNgrams because NGrams allow partial searches across white space:
        i.e. data sci - > data science, but not data analysis or scientific method
        ---
        parameters:
            - name: q
              description: "Search text"
              paramType: query
              required: true
              type: string
        """
        query = request.query_params.get('q')
        if not query:
            raise ParseError("The 'q' querystring parameter is required for searching.")
        course_runs, programs = self.get_results(query)
        data = {'course_runs': course_runs, 'programs': programs}
        serializer = serializers.TypeaheadSearchSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)
