from django_elasticsearch_dsl_drf.serializers import DocumentSerializer
from rest_framework import serializers

from course_discovery.apps.api.fields import StdImageSerializerField
from course_discovery.apps.api.serializers import ContentTypeSerializer
from course_discovery.apps.learner_pathway.api.serializers import LearnerPathwaySerializer, LearnerPathwayStepSerializer

from ..constants import BASE_SEARCH_INDEX_FIELDS, COMMON_IGNORED_FIELDS
from ..documents import LearnerPathwayDocument
from .common import DateTimeSerializerMixin, DocumentDSLSerializerMixin, ModelObjectDocumentSerializerMixin

__all__ = ('LearnerPathwaySearchDocumentSerializer',)


class LearnerPathwaySearchDocumentSerializer(
    ModelObjectDocumentSerializerMixin,
    DocumentSerializer,
    DateTimeSerializerMixin
):
    """
    Serializer for LearnerPathway elasticsearch document.
    """

    steps = LearnerPathwayStepSerializer(many=True, source='object.steps')
    banner_image = StdImageSerializerField(source='object.banner_image')
    card_image = StdImageSerializerField(source='object.card_image')
    created = serializers.SerializerMethodField()

    def get_created(self, obj):
        return self.handle_datetime_field(obj.created)

    class Meta:
        """
        Meta options.
        """

        document = LearnerPathwayDocument
        ignore_fields = COMMON_IGNORED_FIELDS
        fields = (
            BASE_SEARCH_INDEX_FIELDS + (
                'uuid', 'title', 'status', 'banner_image', 'card_image', 'overview', 'published', 'skills',
                'skill_names', 'partner', 'steps', 'visible_via_association', 'created',
            )
        )

    def to_representation(self, instance):
        _object = self.get_model_object_by_instance(instance)
        setattr(instance, 'object', _object)  # pylint: disable=literal-used-as-attribute
        return super().to_representation(instance)


class LearnerPathwaySearchModelSerializer(DocumentDSLSerializerMixin, ContentTypeSerializer, LearnerPathwaySerializer):
    """
    Serializer for LearnerPathway model elasticsearch document.
    """

    class Meta(LearnerPathwaySerializer.Meta):
        """
        Meta options.
        """

        document = LearnerPathwayDocument
        fields = ContentTypeSerializer.Meta.fields + LearnerPathwaySerializer.Meta.fields
