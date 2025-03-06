""" Serializers for api/v2/search/all """

from course_discovery.apps.course_metadata.search_indexes import documents
from course_discovery.apps.course_metadata.search_indexes.constants import SEARCH_INDEX_ADDITIONAL_FIELDS_V2
from course_discovery.apps.course_metadata.search_indexes.documents import (
    CourseDocument, CourseRunDocument, LearnerPathwayDocument, PersonDocument, ProgramDocument
)
from course_discovery.apps.course_metadata.search_indexes.serializers.aggregation import (
    AggregateSearchListSerializer, AggregateSearchSerializer
)
from course_discovery.apps.course_metadata.search_indexes.serializers.common import SortFieldMixin
from course_discovery.apps.course_metadata.search_indexes.serializers.course import CourseSearchDocumentSerializer
from course_discovery.apps.course_metadata.search_indexes.serializers.course_run import (
    CourseRunSearchDocumentSerializer
)
from course_discovery.apps.course_metadata.search_indexes.serializers.learner_pathway import (
    LearnerPathwaySearchDocumentSerializer
)
from course_discovery.apps.course_metadata.search_indexes.serializers.person import PersonSearchDocumentSerializer
from course_discovery.apps.course_metadata.search_indexes.serializers.program import ProgramSearchDocumentSerializer
from course_discovery.apps.edx_elasticsearch_dsl_extensions.serializers import DummyDocument


class CourseRunSearchDocumentSerializerV2(SortFieldMixin, CourseRunSearchDocumentSerializer):
    """
    Serializer for Course Run documents, extending the base `CourseRunSearchDocumentSerializer`
    to include additional fields for enhanced search functionality, as well as a `sort` field
    to provide sorting information from the Elasticsearch response.

    This serializer expands the `fields` attribute in the `Meta` class to include additional
    fields specified in `SEARCH_INDEX_ADDITIONAL_FIELDS_V2`.
    """

    class Meta(CourseRunSearchDocumentSerializer.Meta):
        document = CourseRunDocument
        ignore_fields = CourseRunSearchDocumentSerializer.Meta.ignore_fields
        fields = CourseRunSearchDocumentSerializer.Meta.fields + SEARCH_INDEX_ADDITIONAL_FIELDS_V2


class CourseSearchDocumentSerializerV2(SortFieldMixin, CourseSearchDocumentSerializer):
    """
    Serializer for Course documents, extending the base `CourseSearchDocumentSerializer`
    to include additional fields for enhanced search functionality, as well as a `sort` field
    to provide sorting information from the Elasticsearch response.

    This serializer expands the `fields` attribute in the `Meta` class to include additional
    fields specified in `SEARCH_INDEX_ADDITIONAL_FIELDS_V2`.
    """

    class Meta(CourseSearchDocumentSerializer.Meta):
        document = CourseDocument
        list_serializer_class = CourseSearchDocumentSerializer.Meta.list_serializer_class
        ignore_fields = CourseSearchDocumentSerializer.Meta.ignore_fields
        fields = CourseSearchDocumentSerializer.Meta.fields + SEARCH_INDEX_ADDITIONAL_FIELDS_V2


class ProgramSearchDocumentSerializerV2(SortFieldMixin, ProgramSearchDocumentSerializer):
    """
    Serializer for Program documents, extending the base `ProgramSearchDocumentSerializer`
    to include additional fields for enhanced search functionality, as well as a `sort` field
    to provide sorting information from the Elasticsearch response.

    This serializer expands the `fields` attribute in the `Meta` class to include additional
    fields specified in `SEARCH_INDEX_ADDITIONAL_FIELDS_V2`.
    """

    class Meta(ProgramSearchDocumentSerializer.Meta):
        document = ProgramDocument
        ignore_fields = ProgramSearchDocumentSerializer.Meta.ignore_fields
        fields = ProgramSearchDocumentSerializer.Meta.fields + SEARCH_INDEX_ADDITIONAL_FIELDS_V2


class LearnerPathwaySearchDocumentSerializerV2(SortFieldMixin, LearnerPathwaySearchDocumentSerializer):
    """
    Serializer for Learner Pathway documents, extending the base `LearnerPathwaySearchDocumentSerializer`
    to include additional fields for enhanced search functionality, as well as a `sort` field
    to provide sorting information from the Elasticsearch response.

    This serializer expands the `fields` attribute in the `Meta` class to include additional
    fields specified in `SEARCH_INDEX_ADDITIONAL_FIELDS_V2`.
    """

    class Meta(LearnerPathwaySearchDocumentSerializer.Meta):
        document = LearnerPathwayDocument
        list_serializer_class = LearnerPathwaySearchDocumentSerializer.Meta.list_serializer_class
        ignore_fields = LearnerPathwaySearchDocumentSerializer.Meta.ignore_fields
        fields = LearnerPathwaySearchDocumentSerializer.Meta.fields + SEARCH_INDEX_ADDITIONAL_FIELDS_V2


class PersonSearchDocumentSerializerV2(SortFieldMixin, PersonSearchDocumentSerializer):
    """
    Serializer for Person documents, extending the base `PersonSearchDocumentSerializer`
    to include additional fields for enhanced search functionality, as well as a `sort` field
    to provide sorting information from the Elasticsearch response.

    This serializer expands the `fields` attribute in the `Meta` class to include additional
    fields specified in `SEARCH_INDEX_ADDITIONAL_FIELDS_V2`.
    """

    class Meta(PersonSearchDocumentSerializer.Meta):
        document = PersonDocument
        ignore_fields = PersonSearchDocumentSerializer.Meta.ignore_fields
        fields = PersonSearchDocumentSerializer.Meta.fields + SEARCH_INDEX_ADDITIONAL_FIELDS_V2


# pylint: disable=abstract-method
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


class AggregateSearchSerializerV2(AggregateSearchSerializer):
    """
    Serializer for aggregated elasticsearch documents.
    """

    class Meta(AggregateSearchSerializer.Meta):
        """
        Meta options.
        """

        list_serializer_class = AggregateSearchListSerializerV2
        ignore_fields = AggregateSearchSerializer.Meta.ignore_fields
        document = DummyDocument
