from django_elasticsearch_dsl_drf.serializers import DocumentSerializer
from rest_framework import serializers

from course_discovery.apps.api.serializers import ContentTypeSerializer, MinimalPersonSerializer
from course_discovery.apps.edx_elasticsearch_dsl_extensions.serializers import BaseDjangoESDSLFacetSerializer

from ..constants import BASE_SEARCH_INDEX_FIELDS, COMMON_IGNORED_FIELDS
from ..documents import PersonDocument
from .common import DocumentDSLSerializerMixin

__all__ = ('PersonSearchDocumentSerializer',)


class PersonSearchDocumentSerializer(DocumentSerializer):
    """
    Serializer for a person elasticsearch document.
    """

    profile_image_url = serializers.SerializerMethodField()

    def get_profile_image_url(self, instance):
        return instance.get_profile_image_url

    class Meta:
        """
        Meta options.
        """

        document = PersonDocument
        ignore_fields = COMMON_IGNORED_FIELDS
        fields = BASE_SEARCH_INDEX_FIELDS + (
            'uuid',
            'salutation',
            'full_name',
            'bio',
            'bio_language',
            'profile_image_url',
            'position',
            'organizations',
        )


# pylint: disable=abstract-method
class PersonFacetSerializer(BaseDjangoESDSLFacetSerializer):
    """
    Serializer for person facets elasticsearch document.
    """

    class Meta:
        """
        Meta options.
        """

        ignore_fields = COMMON_IGNORED_FIELDS
        fields = ('organizations',)


class PersonSearchModelSerializer(DocumentDSLSerializerMixin, ContentTypeSerializer, MinimalPersonSerializer):
    """
    Serializer for person model elasticsearch document.
    """

    class Meta(MinimalPersonSerializer.Meta):
        """
        Meta options.
        """

        document = PersonDocument
        fields = ContentTypeSerializer.Meta.fields + MinimalPersonSerializer.Meta.fields
