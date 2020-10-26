import uuid

from django.db.models import Q
from django.http import QueryDict
from drf_haystack.filters import HaystackFilter, HaystackOrderingFilter
from drf_haystack.mixins import FacetMixin
from drf_haystack.viewsets import HaystackViewSet
from haystack.backends import SQ
from haystack.inputs import AutoQuery
from haystack.query import SearchQuerySet
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ParseError, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import BrowsableAPIRenderer, JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from course_discovery.apps.api import filters, mixins, serializers
from course_discovery.apps.course_metadata.choices import ProgramStatus
from course_discovery.apps.course_metadata.models import Course, CourseRun, Person, Program


# pylint: disable=useless-super-delegation
class BaseHaystackViewSet(mixins.DetailMixin, FacetMixin, HaystackViewSet):
    document_uid_field = 'key'
    facet_filter_backends = [filters.HaystackFacetFilterWithQueries, filters.HaystackFilter, HaystackOrderingFilter]
    ordering_fields = ('aggregation_key', 'start')

    load_all = True
    lookup_field = 'key'
    permission_classes = (IsAuthenticated,)
    ensure_published = True

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
        return super().list(request, *args, **kwargs)

    @action(detail=False, methods=['get'], url_path='facets')
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
        return super().facets(request)

    def filter_facet_queryset(self, queryset):
        queryset = super().filter_facet_queryset(queryset)

        q = self.request.query_params.get('q')
        if q:
            queryset = queryset.filter(SQ(text=AutoQuery(q)) | SQ(title=AutoQuery(q)))

        facet_serializer_cls = self.get_facet_serializer_class()
        field_queries = getattr(facet_serializer_cls.Meta, 'field_queries', {})

        if self.ensure_published:
            # Ensure we only return published, non-hidden items
            queryset = queryset.filter(published=True).exclude(hidden=True)

        for facet in self.request.query_params.getlist('selected_query_facets'):
            query = field_queries.get(facet)

            if not query:
                raise ParseError(f'The selected query facet [{facet}] is not valid.')

            queryset = queryset.raw_search(query['query'])

        return queryset


class CatalogDataFilterBackend(HaystackFilter):

    @staticmethod
    def get_request_filters(request):
        if request.method == 'GET':
            return HaystackFilter.get_request_filters(request)

        request_filters = QueryDict(mutable=True)
        for param, value in request.data.items():
            if isinstance(value, list):
                request_filters.setlist(param, value)
            else:
                request_filters[param] = value

        return request_filters


class BrowsableAPIRendererWithoutForms(BrowsableAPIRenderer):
    """Renders the browsable api without the forms."""

    def get_rendered_html_form(self, data, view, method, request):
        return None

    def get_raw_data_form(self, data, view, method, request):
        return None


class CatalogDataViewSet(viewsets.GenericViewSet):
    renderer_classes = [JSONRenderer, BrowsableAPIRendererWithoutForms]
    permission_classes = (IsAuthenticated,)
    filter_backends = (CatalogDataFilterBackend, HaystackOrderingFilter)

    def create(self, request):
        return self.list(request)  # pylint: disable=no-member


class CourseSearchViewSet(BaseHaystackViewSet):
    index_models = (Course,)
    detail_serializer_class = serializers.CourseSearchModelSerializer
    facet_serializer_class = serializers.CourseFacetSerializer
    serializer_class = serializers.CourseSearchSerializer


class CourseRunSearchViewSet(BaseHaystackViewSet):
    index_models = (CourseRun,)
    detail_serializer_class = serializers.CourseRunSearchModelSerializer
    facet_serializer_class = serializers.CourseRunFacetSerializer
    serializer_class = serializers.CourseRunSearchSerializer


class ProgramSearchViewSet(BaseHaystackViewSet):
    document_uid_field = 'uuid'
    lookup_field = 'uuid'
    index_models = (Program,)
    detail_serializer_class = serializers.ProgramSearchModelSerializer
    facet_serializer_class = serializers.ProgramFacetSerializer
    serializer_class = serializers.ProgramSearchSerializer


class AggregateSearchViewSet(BaseHaystackViewSet, CatalogDataViewSet):
    """ Search all content types. """
    detail_serializer_class = serializers.AggregateSearchModelSerializer
    facet_serializer_class = serializers.AggregateFacetSearchSerializer
    serializer_class = serializers.AggregateSearchSerializer


class LimitedAggregateSearchView(FacetMixin, HaystackViewSet):
    """
    The purpose of this endpoint is to provide search data in the correct order to
    consume the ordering for another service. We will be providing a limited
    set of data based on what exists in the search indexes. Other types of
    ordering are not supported.
    """
    document_uid_field = 'key'
    facet_filter_backends = [filters.HaystackFilter]

    lookup_field = 'key'
    permission_classes = (IsAuthenticated,)
    facet_serializer_class = serializers.AggregateFacetSearchSerializer
    serializer_class = serializers.LimitedAggregateSearchSerializer

    def filter_facet_queryset(self, queryset):
        queryset = super().filter_facet_queryset(queryset)

        # Ensure we only return published, non-hidden items
        queryset = queryset.filter(published=True).exclude(hidden=True)

        return queryset


class PersonSearchViewSet(BaseHaystackViewSet):
    """
    Generic person search
    """
    permission_classes = (IsAuthenticated,)
    index_models = (Person,)
    filter_backends = (CatalogDataFilterBackend, HaystackOrderingFilter)
    detail_serializer_class = serializers.PersonSearchModelSerializer
    facet_serializer_class = serializers.PersonFacetSerializer
    serializer_class = serializers.PersonSearchSerializer
    ensure_published = False
    document_uid = 'uuid'
    lookup_field = 'uuid'


class PersonTypeaheadSearchView(APIView):
    """ Typeahead for people. """
    permission_classes = (IsAuthenticated,)

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
            - name: orgs
              description: "Organization short codes"
              paramType: query
              required: false
              type: List of string
        """
        query = request.query_params.get('q')
        if not query:
            raise ValidationError("The 'q' querystring parameter is required for searching.")
        words = query.split()
        org_keys = self.request.GET.getlist('org', None)

        queryset = Person.objects.all()

        if org_keys:
            # We are pulling the people who are part of course runs belonging to the given organizations.
            # This blank order_by is there to offset the default ordering on people since
            # we don't care about the order in which they are returned.
            queryset = queryset.filter(
                courses_staffed__course__authoring_organizations__key__in=org_keys
            ).distinct().order_by()

        for word in words:
            # Progressively filter the same queryset - every word must match something
            queryset = queryset.filter(Q(given_name__icontains=word) | Q(family_name__icontains=word))

        # No match? Maybe they gave us a UUID...
        if not queryset:
            try:
                q_uuid = uuid.UUID(query).hex
                queryset = Person.objects.filter(uuid=q_uuid)
            except ValueError:
                pass

        context = {'request': self.request}
        serialized_people = [serializers.PersonSerializer(p, context=context).data for p in queryset]
        return Response(serialized_people, status=status.HTTP_200_OK)


class TypeaheadSearchView(APIView):
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

            seen_course_keys.add(course_key)
            course_run_list.append(course_run)

            if len(course_run_list) == self.RESULT_COUNT:
                break

        programs = sqs.models(Program).filter(
            SQ(title_autocomplete=clean_query) |
            SQ(authoring_organizations_autocomplete=clean_query)
        )
        programs = programs.filter(status=ProgramStatus.Active).exclude(hidden=True).filter(partner=partner.short_code)
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
        partner = request.site.partner
        if not query:
            raise ValidationError("The 'q' querystring parameter is required for searching.")
        course_runs, programs = self.get_results(query, partner)
        data = {'course_runs': course_runs, 'programs': programs}
        serializer = serializers.TypeaheadSearchSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)
