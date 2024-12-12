# pylint: disable=W0223
from django.db import models
from django_elasticsearch_dsl_drf.serializers import DocumentSerializer
from rest_framework import serializers
from rest_framework.serializers import ListSerializer

from course_discovery.apps.api.fields import StdImageSerializerField
from course_discovery.apps.api.serializers import ContentTypeSerializer
from course_discovery.apps.learner_pathway.api.serializers import LearnerPathwaySerializer, LearnerPathwayStepSerializer

from ..constants import BASE_SEARCH_INDEX_FIELDS, COMMON_IGNORED_FIELDS
from ..documents import LearnerPathwayDocument
from .common import DateTimeSerializerMixin, DocumentDSLSerializerMixin, ModelObjectDocumentSerializerMixin

__all__ = ('LearnerPathwaySearchDocumentSerializer',)


class LearnerPathwaySearchDocumentListSerializer(ModelObjectDocumentSerializerMixin, ListSerializer):
    def to_representation(self, data):
        """
        Custom list representation to fetch all the learner_pathway instances at once.
        """
        iterable = data.all() if isinstance(data, models.Manager) else data
        _objects = list(self.get_model_object_by_instances(iterable))

        object_dict = {obj.pk: obj for obj in _objects}
        result_tuples = [(item, object_dict.get(item.pk)) for item in iterable]

        return super().to_representation(result_tuples)


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

        list_serializer_class = LearnerPathwaySearchDocumentListSerializer
        document = LearnerPathwayDocument
        ignore_fields = COMMON_IGNORED_FIELDS
        fields = (
            BASE_SEARCH_INDEX_FIELDS + (
                'uuid', 'title', 'status', 'banner_image', 'card_image', 'overview', 'published', 'skills',
                'skill_names', 'partner', 'steps', 'visible_via_association', 'created',
            )
        )

    def to_representation(self, instance):
        """
        Custom instance representation.
        The instance needs to be handled differently and can be either of the two:

        1. A tuple consistent of an ES Hit object and a model object to be assigned to the hit object.
        2. A single ES Hit object
        """
        if isinstance(instance, tuple):
            setattr(instance[0], 'object', instance[1])  # pylint: disable=literal-used-as-attribute
            prepared_instance = instance[0]
        else:
            _object = self.get_model_object_by_instances(instance).get()
            setattr(instance, 'object', _object)  # pylint: disable=literal-used-as-attribute
            prepared_instance = instance
        return super().to_representation(prepared_instance)


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
