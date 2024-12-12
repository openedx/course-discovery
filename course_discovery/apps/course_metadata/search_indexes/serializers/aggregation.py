from django.db import models
from django_elasticsearch_dsl_drf.serializers import DocumentSerializer
from rest_framework.serializers import ListSerializer

from course_discovery.apps.api.serializers import COMMON_IGNORED_FIELDS
from course_discovery.apps.course_metadata.search_indexes import documents
from course_discovery.apps.edx_elasticsearch_dsl_extensions.serializers import (
    BaseDjangoESDSLFacetSerializer, DummyDocument, MultiDocumentSerializerMixin
)

from .course import CourseSearchDocumentSerializer, CourseSearchDocumentSerializerV2, CourseSearchModelSerializer
from .course_run import (
    CourseRunSearchDocumentSerializer, CourseRunSearchDocumentSerializerV2, CourseRunSearchModelSerializer
)
from .learner_pathway import (
    LearnerPathwaySearchDocumentSerializer, LearnerPathwaySearchDocumentSerializerV2,
    LearnerPathwaySearchModelSerializer
)
from .person import PersonSearchDocumentSerializer, PersonSearchDocumentSerializerV2
from .program import ProgramSearchDocumentSerializer, ProgramSearchDocumentSerializerV2, ProgramSearchModelSerializer


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


class AggregateSearchListSerializer(MultiDocumentSerializerMixin, ListSerializer):
    """
    Custom List Serializer for AggregateSearch to fetch all instances at once.
    """
    def to_representation(self, data):
        """
        Custom representation for all the grouped multi-serializer instances.
        This will invoke the respective custom list serializers for all the documents.
        """
        iterable = data.all() if isinstance(data, models.Manager) else data
        grouped_instances = self.group_multi_serializer_instances(iterable)

        representations = []

        for serializer_class, instances_for_serializer in grouped_instances.items():
            representations += serializer_class(
                context=self._context, many=True
            ).to_representation(instances_for_serializer)

        return representations

    class Meta:
        """
        Meta options.
        """
        serializers = {
            documents.CourseRunDocument: CourseRunSearchDocumentSerializer,
            documents.CourseDocument: CourseSearchDocumentSerializer,
            documents.ProgramDocument: ProgramSearchDocumentSerializer,
            documents.LearnerPathwayDocument: LearnerPathwaySearchDocumentSerializer,
            documents.PersonDocument: PersonSearchDocumentSerializer,
        }


class AggregateSearchListSerializerV2(AggregateSearchListSerializer):
    """
    Extended version of the AggregateSearchListSerializer with updated serializers that support search_after pagination.

    This subclass allows for the use of newer serializer versions for the same document types,
    which include additional search index fields specifically for version 2.
    """

    class Meta(AggregateSearchListSerializer.Meta):
        """
        Meta options.
        """
        serializers = {
            documents.CourseRunDocument: CourseRunSearchDocumentSerializerV2,
            documents.CourseDocument: CourseSearchDocumentSerializerV2,
            documents.ProgramDocument: ProgramSearchDocumentSerializerV2,
            documents.LearnerPathwayDocument: LearnerPathwaySearchDocumentSerializerV2,
            documents.PersonDocument: PersonSearchDocumentSerializerV2,
        }


class AggregateSearchSerializer(DocumentSerializer):
    """
    Serializer for aggregated elasticsearch documents.
    """

    class Meta:
        """
        Meta options.
        """
        list_serializer_class = AggregateSearchListSerializer
        document = DummyDocument
        ignore_fields = COMMON_IGNORED_FIELDS


class AggregateSearchSerializerV2(AggregateSearchSerializer):
    """
    Serializer for aggregated elasticsearch documents.
    """

    class Meta(AggregateSearchSerializer.Meta):
        """
        Meta options.
        """
        list_serializer_class = AggregateSearchListSerializerV2
        document = DummyDocument
