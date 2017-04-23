from drf_haystack.mixins import FacetMixin
from drf_haystack.viewsets import HaystackViewSet
from haystack.backends import SQ
from haystack.inputs import AutoQuery
from haystack.query import SearchQuerySet
from rest_framework import status
from rest_framework.decorators import list_route
from rest_framework.exceptions import NotFound, ParseError, ValidationError
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from course_discovery.apps.api import filters, serializers
from course_discovery.apps.api.v1.views import PartnerMixin
from course_discovery.apps.course_metadata.choices import ProgramStatus
from course_discovery.apps.course_metadata.models import Course, CourseRun, Program


class BaseHaystackViewSet(FacetMixin, HaystackViewSet):
    document_uid_field = 'key'
    facet_filter_backends = [filters.HaystackFacetFilterWithQueries, filters.HaystackFilter, OrderingFilter]
    ordering_fields = ('start',)

    load_all = True
    lookup_field = 'key'
    permission_classes = (IsAuthenticated,)

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

        Overrides and re-implement FacetsMixin.facets so that we can populate the queryset cache before passing it to
        the serializer and avoid making extra search queries. Original implimentation:
        https://github.com/inonit/drf-haystack/blob/master/drf_haystack/mixins.py#L47
        """
        queryset = self.filter_facet_queryset(self.get_queryset())

        for facet in request.query_params.getlist("selected_facets"):

            if ":" not in facet:
                continue

            field, value = facet.split(":", 1)
            if value:
                queryset = queryset.narrow('%s:"%s"' % (field, queryset.query.clean(value)))

        # Run the query and populate the cache before passing the queryset to the serializer, to prevent extra
        # queries from running.
        self.populate_queryset_cache(queryset, request)
        serializer = self.get_facet_serializer(queryset.facet_counts(), objects=queryset, many=False)
        return Response(serializer.data)

    def populate_queryset_cache(self, queryset, request):
        """ Execute the query and populate the cache with the results for the requested page/page_size."""
        pagination_instance = self.pagination_class()
        page_size = pagination_instance.get_page_size(request)
        page_number = request.query_params.get(pagination_instance.page_query_param, 1)

        # If page_number is something like 'last', we have no way to infer what the actual page number should
        # be. Set it to one so that we can at least warm the cache for the calls to facet_counts and count
        # that will come later, even though we'll probably still have to run an additional query to actually
        # get the results.
        if page_number in pagination_instance.last_page_strings:
            page_number = 1

        # Page number validation logic borrowed from the django.core.Paginator:
        # https://github.com/django/django/blob/1.9.12/django/core/paginator.py#L29
        try:
            page_number = int(page_number)
        except (TypeError, ValueError):
            raise NotFound('Invalid page.')
        if page_number < 1:
            raise NotFound('Invalid page.')

        start = (page_number - 1) * page_size
        end = start + page_size
        queryset._fill_cache(start, end)  # pylint: disable=protected-access

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


class TypeaheadSearchView(PartnerMixin, APIView):
    """ Typeahead for courses and programs. """
    RESULT_COUNT = 3
    permission_classes = (IsAuthenticated,)

    def get_results(self, query, partner):
        sqs = SearchQuerySet()
        clean_query = sqs.query.clean(query)

        course_runs = sqs.models(CourseRun).filter(
            SQ(title_autocomplete=clean_query) |
            SQ(course_key=clean_query) |
            SQ(authoring_organizations_autocomplete=clean_query)
        )
        course_runs = course_runs.filter(published=True).exclude(hidden=True).filter(partner=partner.short_code)

        # Get first three results after deduplicating by course key.
        seen_course_keys, course_run_list = set(), []
        for course_run in course_runs:
            course_key = course_run.course_key

            if course_key in seen_course_keys:
                continue
            else:
                seen_course_keys.add(course_key)
                course_run_list.append(course_run)

            if len(course_run_list) == self.RESULT_COUNT:
                break

        programs = sqs.models(Program).filter(
            SQ(title_autocomplete=clean_query) |
            SQ(authoring_organizations_autocomplete=clean_query)
        )
        programs = programs.filter(status=ProgramStatus.Active).filter(partner=partner.short_code)
        programs = programs[:self.RESULT_COUNT]

        return course_run_list, programs

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
            - name: partner
              description: "Partner short code"
              paramType: query
              required: false
              type: string
        """
        query = request.query_params.get('q')
        partner = self.get_partner()
        if not query:
            raise ValidationError("The 'q' querystring parameter is required for searching.")
        course_runs, programs = self.get_results(query, partner)
        data = {'course_runs': course_runs, 'programs': programs}
        serializer = serializers.TypeaheadSearchSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)
