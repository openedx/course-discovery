from django_elasticsearch_dsl_drf.serializers import DocumentSerializer

from course_discovery.apps.api.serializers import COMMON_IGNORED_FIELDS
from course_discovery.apps.course_metadata.search_indexes import documents
from course_discovery.apps.edx_elasticsearch_dsl_extensions.serializers import (
    BaseDjangoESDSLFacetSerializer, DummyDocument, MultiDocumentSerializerMixin
)

from .course import CourseSearchDocumentSerializer, CourseSearchModelSerializer
from .course_run import CourseRunSearchDocumentSerializer, CourseRunSearchModelSerializer
from .learner_pathway import LearnerPathwaySearchDocumentSerializer, LearnerPathwaySearchModelSerializer
from .person import PersonSearchDocumentSerializer
from .program import ProgramSearchDocumentSerializer, ProgramSearchModelSerializer


class AggregateSearchModelSerializer(MultiDocumentSerializerMixin, DocumentSerializer):
    """
    Serializer for aggregated model elasticsearch documents.
    """

    class Meta:
        """
        Meta options.
        """
        document = DummyDocument

        serializers = {
            documents.CourseRunDocument: CourseRunSearchModelSerializer,
            documents.CourseDocument: CourseSearchModelSerializer,
            documents.LearnerPathwayDocument: LearnerPathwaySearchModelSerializer,
            documents.ProgramDocument: ProgramSearchModelSerializer,
        }


# pylint: disable=abstract-method
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
            documents.CourseRunDocument: CourseRunSearchDocumentSerializer,
            documents.CourseDocument: CourseSearchDocumentSerializer,
            documents.ProgramDocument: ProgramSearchDocumentSerializer,
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
        serializers = {
            documents.CourseRunDocument: CourseRunSearchDocumentSerializer,
            documents.CourseDocument: CourseSearchDocumentSerializer,
            documents.ProgramDocument: ProgramSearchDocumentSerializer,
            documents.LearnerPathwayDocument: LearnerPathwaySearchDocumentSerializer,
            documents.PersonDocument: PersonSearchDocumentSerializer,
        }
