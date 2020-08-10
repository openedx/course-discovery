from django_elasticsearch_dsl_drf.serializers import DocumentSerializer

from course_discovery.apps.api.serializers import COMMON_IGNORED_FIELDS
from course_discovery.apps.course_metadata.search_indexes import documents
from course_discovery.apps.edx_haystack_extensions.serializers import (
    BaseDjangoESDSLFacetSerializer,
    DummyDocument,
    MultiDocumentSerializerMixin,
)
from .course import CourseSearchDocumentSerializer
from .course_run import CourseRunSearchDocumentSerializer
from .person import PersonSearchDocumentSerializer
from .program import ProgramSearchDocumentSerializer


class AggregateSearchModelSerializer(MultiDocumentSerializerMixin, DocumentSerializer):
    """
    Serializer for aggregated model elasticsearch documents.
    """

    class Meta:
        """
        Meta options.
        """

        serializers = {
            documents.CourseRunDocument._index._name: CourseRunSearchDocumentSerializer,
            documents.CourseDocument._index._name: CourseSearchDocumentSerializer,
            documents.ProgramDocument._index._name: ProgramSearchDocumentSerializer,
        }


class AggregateFacetSearchSerializer(BaseDjangoESDSLFacetSerializer):
    """
    Serializer for aggregated facets elasticsearch documents.
    """

    class Meta:
        """
        Meta options.
        """

        ignore_fields = COMMON_IGNORED_FIELDS


class LimitedAggregateSearchSerializer(MultiDocumentSerializerMixin, DocumentSerializer):
    """
    Serializer for limited aggregated elasticsearch documents.
    """

    class Meta:
        """
        Meta options.
        """

        document = DummyDocument
        ignore_fields = COMMON_IGNORED_FIELDS
        fields = [
            'partner',
            'authoring_organization_uuids',
            'subject_uuids',
            'uuid',
            'key',
            'aggregation_key',
            'content_type',
        ]
        serializers = {
            documents.CourseRunDocument._index._name: CourseRunSearchDocumentSerializer,
            documents.CourseDocument._index._name: CourseSearchDocumentSerializer,
            documents.ProgramDocument._index._name: ProgramSearchDocumentSerializer,
        }


class AggregateSearchSerializer(MultiDocumentSerializerMixin, DocumentSerializer):
    """
    Serializer for aggregated elasticsearch documents.
    """

    class Meta:
        """
        Meta options.
        """

        document = DummyDocument
        ignore_fields = COMMON_IGNORED_FIELDS
        fields = (
            CourseRunSearchDocumentSerializer.Meta.fields
            + ProgramSearchDocumentSerializer.Meta.fields
            + CourseSearchDocumentSerializer.Meta.fields
        )
        serializers = {
            documents.CourseRunDocument._index._name: CourseRunSearchDocumentSerializer,
            documents.CourseDocument._index._name: CourseSearchDocumentSerializer,
            documents.ProgramDocument._index._name: ProgramSearchDocumentSerializer,
            documents.PersonDocument._index._name: PersonSearchDocumentSerializer,
        }
