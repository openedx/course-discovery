import uuid

from django.conf import settings
from django.db.models import Q as DQ
from django_elasticsearch_dsl_drf.constants import LOOKUP_FILTER_TERM, LOOKUP_FILTER_TERMS
from django_elasticsearch_dsl_drf.filter_backends import DefaultOrderingFilterBackend, OrderingFilterBackend
from elasticsearch_dsl.query import Q as ESDSLQ
from rest_framework import status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import BrowsableAPIRenderer, JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from course_discovery.apps.api import serializers
from course_discovery.apps.api.utils import update_query_params_with_body_data
from course_discovery.apps.course_metadata.choices import ProgramStatus
from course_discovery.apps.course_metadata.models import Person
from course_discovery.apps.course_metadata.search_indexes import documents as search_documents
from course_discovery.apps.course_metadata.search_indexes import serializers as search_indexes_serializers
from course_discovery.apps.edx_elasticsearch_dsl_extensions.backends import (
    AggregateDataFilterBackend, CatalogDataFilterBackend, MultiMatchSearchFilterBackend
)
from course_discovery.apps.edx_elasticsearch_dsl_extensions.viewsets import (
    BaseElasticsearchDocumentViewSet, MultiDocumentsWrapper
)


class FacetQueryFieldsMixin:
    """
    Facet query fields mixin.

    Provides faceted query filter fields.
    Query cases:
        - availability_current
        - availability_starting_soon
        - availability_upcoming
        - availability_archived
    """

    faceted_query_filter_fields = {
        'availability_current': {
            'query': [ESDSLQ('range', start={"lte": "now"}), ESDSLQ('range', end={"gte": "now"})],
            'enabled': True,
        },
        'availability_starting_soon': {
            'query': [ESDSLQ('range', start={"lte": "now+60d", "gte": "now"})],
            'enabled': True,
        },
        'availability_upcoming': {'query': [ESDSLQ('range', start={"gte": "now+60d"})], 'enabled': True},
        'availability_archived': {'query': [ESDSLQ('range', end={"lte": "now"})], 'enabled': True},
    }


class BrowsableAPIRendererWithoutForms(BrowsableAPIRenderer):
    """Renders the browsable api without the forms."""

    def get_rendered_html_form(self, data, view, method, request):
        return None

    def get_raw_data_form(self, data, view, method, request):
        return None


class CatalogDataViewSet(viewsets.GenericViewSet):
    """
    Catalog data viewset
    """

    renderer_classes = [JSONRenderer, BrowsableAPIRendererWithoutForms]
    permission_classes = (IsAuthenticated,)
    filter_backends = [CatalogDataFilterBackend, OrderingFilterBackend]

    @update_query_params_with_body_data
    def create(self, request):
        return self.list(request)  # pylint: disable=no-member


class CourseSearchViewSet(BaseElasticsearchDocumentViewSet):
    """
    Course search viewset
    """

    document = search_documents.CourseDocument
    detail_serializer_class = search_indexes_serializers.CourseSearchModelSerializer
    facet_serializer_class = search_indexes_serializers.CourseFacetSerializer
    serializer_class = search_indexes_serializers.CourseSearchDocumentSerializer
    faceted_search_fields = {
        'level_type': {'field': 'level_type.raw', 'enabled': True},
        'organizations': {
            'field': 'organizations.raw',
            'enabled': True,
            'options': {"size": settings.SEARCH_FACET_LIMIT},
        },
        'subjects': {'field': 'subjects.raw', 'enabled': True},
        'prerequisites': {'field': 'prerequisites', 'enabled': True},
    }


class CourseRunSearchViewSet(FacetQueryFieldsMixin, BaseElasticsearchDocumentViewSet):
    """
    CourseRun search viewset.
    """

    detail_serializer_class = search_indexes_serializers.CourseRunSearchModelSerializer
    document = search_documents.CourseRunDocument
    serializer_class = search_indexes_serializers.CourseRunSearchDocumentSerializer
    facet_serializer_class = search_indexes_serializers.CourseRunFacetSerializer
    faceted_search_fields = {
        'language': {'field': 'language.raw', 'enabled': True},
        'level_type': {'field': 'level_type.raw', 'enabled': True},
        'mobile_available': {'field': 'mobile_available', 'enabled': True},
        'organizations': {
            'field': 'organizations.raw',
            'enabled': True,
            'options': {"size": settings.SEARCH_FACET_LIMIT},
        },
        'pacing_type': {'field': 'pacing_type', 'enabled': True},
        'first_enrollable_paid_seat_price': {'field': 'first_enrollable_paid_seat_price', 'enabled': True},
        'seat_types': {'field': 'seat_types', 'enabled': True},
        'subjects': {'field': 'subjects.raw', 'enabled': True},
        'transcript_languages': {'field': 'transcript_languages.raw', 'enabled': True},
        'content_type': {'field': 'content_type', 'enabled': True},
    }


class ProgramSearchViewSet(BaseElasticsearchDocumentViewSet):
    """
    Program search viewset.
    """

    document_uid_field = 'uuid'
    lookup_field = 'uuid'
    document = search_documents.ProgramDocument
    detail_serializer_class = search_indexes_serializers.ProgramSearchModelSerializer
    facet_serializer_class = search_indexes_serializers.ProgramFacetSerializer
    serializer_class = search_indexes_serializers.ProgramSearchDocumentSerializer
    faceted_search_fields = {
        'type': {'field': 'type.raw', 'enabled': True},
        'status': {'field': 'status', 'enabled': True},
        'seat_types': {'field': 'seat_types', 'enabled': True},
    }


class BaseAggregateSearchViewSet(FacetQueryFieldsMixin, BaseElasticsearchDocumentViewSet):
    """
    Base aggregate search viewset.
    """

    lookup_field = 'uuid'
    document_uid_field = 'uuid'
    facet_serializer_class = search_indexes_serializers.AggregateFacetSearchSerializer

    faceted_search_fields = {
        'language': {'field': 'language.raw', 'enabled': True},
        'level_type': {'field': 'level_type.raw', 'enabled': True},
        'mobile_available': {'field': 'mobile_available', 'enabled': True},
        'organizations': {
            'field': 'organizations.raw',
            'enabled': True,
            'options': {"size": settings.SEARCH_FACET_LIMIT},
        },
        'pacing_type': {'field': 'pacing_type', 'enabled': True},
        'first_enrollable_paid_seat_price': {'field': 'first_enrollable_paid_seat_price', 'enabled': True},
        'seat_types': {'field': 'seat_types', 'enabled': True},
        'subjects': {'field': 'subjects.raw', 'enabled': True},
        'transcript_languages': {'field': 'transcript_languages.raw', 'enabled': True},
        'status': {'field': 'status', 'enabled': True},
        'type': {'field': 'type.raw', 'enabled': True},
        'content_type': {'field': 'content_type', 'enabled': True},
    }
    ordering_fields = {'start': 'start', 'aggregation_key': 'aggregation_key'}
    filter_fields = {
        'partner': {'field': 'partner.lower', 'lookups': [LOOKUP_FILTER_TERM]},
        'content_type': {'field': 'content_type', 'lookups': [LOOKUP_FILTER_TERM, LOOKUP_FILTER_TERMS]},
        'aggregation_key': {'field': 'aggregation_key', 'lookups': [LOOKUP_FILTER_TERM, LOOKUP_FILTER_TERMS]},
        'availability': {'field': 'availability.lower', 'lookups': [LOOKUP_FILTER_TERM, LOOKUP_FILTER_TERMS]},
        'key': {'field': 'key', 'lookups': [LOOKUP_FILTER_TERM, LOOKUP_FILTER_TERMS]},
        'level_type': {'field': 'level_type.lower', 'lookups': [LOOKUP_FILTER_TERM, LOOKUP_FILTER_TERMS]},
        'org': {'field': 'org.lower', 'lookups': [LOOKUP_FILTER_TERM, LOOKUP_FILTER_TERMS]},
        'type': {'field': 'type.lower', 'lookups': [LOOKUP_FILTER_TERM]},
        'authoring_organization_uuids': {
            'field': 'authoring_organization_uuids',
            'lookups': [LOOKUP_FILTER_TERM, LOOKUP_FILTER_TERMS]
        },
    }


class AggregateSearchViewSet(BaseAggregateSearchViewSet):
    """
    Search all elasticsearch documents.
    """

    detail_serializer_class = search_indexes_serializers.AggregateSearchModelSerializer
    serializer_class = search_indexes_serializers.AggregateSearchSerializer
    document = MultiDocumentsWrapper(
        search_documents.CourseRunDocument,
        search_documents.PersonDocument,
        search_documents.ProgramDocument,
        search_documents.CourseDocument,
    )
    filter_backends = [
        MultiMatchSearchFilterBackend,
        CatalogDataFilterBackend,
        OrderingFilterBackend,
        DefaultOrderingFilterBackend,
    ]

    @update_query_params_with_body_data
    def create(self, request):
        return self.list(request)


class LimitedAggregateSearchView(BaseAggregateSearchViewSet):
    """
    The purpose of this endpoint is to provide search data in the correct order to
    consume the ordering for another service. We will be providing a limited
    set of data based on what exists in the search indexes. Other types of
    ordering are not supported.
    """

    serializer_class = search_indexes_serializers.LimitedAggregateSearchSerializer
    document = MultiDocumentsWrapper(
        search_documents.CourseRunDocument,
        search_documents.ProgramDocument,
        search_documents.CourseDocument
    )
    filter_backends = [
        MultiMatchSearchFilterBackend,
        AggregateDataFilterBackend,
        OrderingFilterBackend,
        DefaultOrderingFilterBackend,
    ]


class PersonSearchViewSet(BaseElasticsearchDocumentViewSet):
    """
    Generic person search
    """

    lookup_field = 'uuid'
    document_uid_field = 'uuid'
    ensure_published = False
    document = search_documents.PersonDocument
    serializer_class = search_indexes_serializers.PersonSearchDocumentSerializer
    detail_serializer_class = search_indexes_serializers.PersonSearchModelSerializer
    facet_serializer_class = search_indexes_serializers.PersonFacetSerializer
    faceted_search_fields = {'organizations': {'field': 'organizations', 'enabled': True}}
    ordering = ('aggregation_key',)


class PersonTypeaheadSearchView(APIView):
    """ Typeahead for people. """
    permission_classes = (IsAuthenticated,)

    def get(self, request, *_args, **_kwargs):
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
            queryset = (
                queryset.filter(courses_staffed__course__authoring_organizations__key__in=org_keys)
                .distinct()
                .order_by()
            )

        for word in words:
            # Progressively filter the same queryset - every word must match something
            queryset = queryset.filter(DQ(given_name__icontains=word) | DQ(family_name__icontains=word))

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
        course_runs = search_documents.CourseRunDocument.search().query(
            ESDSLQ(
                'bool',
                minimum_should_match=1,
                should=[
                    ESDSLQ('match', title__edge_ngram_completion=query),
                    ESDSLQ('match', title__suggest=query),
                    ESDSLQ('match', title=query),
                    ESDSLQ('match', course_key=query),
                    ESDSLQ('match', authoring_organizations__edge_ngram_completion=query),
                ],
                filter=[ESDSLQ('term', published=True), ESDSLQ('term', partner=partner.short_code)],
                must_not=ESDSLQ('term', hidden=True),
            )
        )

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

        programs = search_documents.ProgramDocument.search().query(
            ESDSLQ(
                'bool',
                minimum_should_match=1,
                should=[
                    ESDSLQ('match', title__edge_ngram_completion=query),
                    ESDSLQ('match', title__suggest=query),
                    ESDSLQ('match', title=query),
                    ESDSLQ('match', authoring_organizations__edge_ngram_completion=query),
                ],
                filter=[ESDSLQ('term', status=ProgramStatus.Active), ESDSLQ('term', partner=partner.short_code)],
                must_not=[ESDSLQ('term', hidden=True)],
            )
        )
        programs = programs[:self.RESULT_COUNT]

        return course_run_list, programs

    def get(self, request, *_args, **_kwargs):
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
