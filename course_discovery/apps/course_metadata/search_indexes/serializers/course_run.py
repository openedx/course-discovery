from django.utils.dateparse import parse_datetime
from django_elasticsearch_dsl_drf.serializers import DocumentSerializer
from rest_framework import serializers

from course_discovery.apps.api.serializers import ContentTypeSerializer, CourseRunWithProgramsSerializer
from course_discovery.apps.core.utils import serialize_datetime
from course_discovery.apps.edx_haystack_extensions.serializers import BaseDjangoESDSLFacetSerializer
from .common import DocumentDSLSerializerMixin
from ..constants import BASE_SEARCH_INDEX_FIELDS, COMMON_IGNORED_FIELDS
from ..documents import CourseRunDocument

__all__ = ('CourseRunSearchDocumentSerializer',)


class CourseRunSearchDocumentSerializer(DocumentSerializer):
    """
    Serializer for course run elasticsearch document.
    """

    start = serializers.SerializerMethodField()
    end = serializers.SerializerMethodField()
    enrollment_start = serializers.SerializerMethodField()
    enrollment_end = serializers.SerializerMethodField()

    @staticmethod
    def handle_datetime_field(value):
        if isinstance(value, str):
            value = parse_datetime(value)
        return serialize_datetime(value)

    def get_start(self, obj):
        return self.handle_datetime_field(obj.start)

    def get_end(self, obj):
        return self.handle_datetime_field(obj.end)

    def get_enrollment_start(self, obj):
        return self.handle_datetime_field(obj.enrollment_start)

    def get_enrollment_end(self, obj):
        return self.handle_datetime_field(obj.enrollment_end)

    class Meta:
        """
        Meta options.
        """

        document = CourseRunDocument
        ignore_fields = COMMON_IGNORED_FIELDS
        fields = BASE_SEARCH_INDEX_FIELDS + (
            'authoring_organization_uuids',
            'availability',
            'end',
            'enrollment_end',
            'enrollment_start',
            'first_enrollable_paid_seat_sku',
            'first_enrollable_paid_seat_price',
            'full_description',
            'go_live_date',
            'has_enrollable_seats',
            'image_url',
            'is_enrollable',
            'key',
            'language',
            'level_type',
            'logo_image_urls',
            'marketing_url',
            'max_effort',
            'min_effort',
            'mobile_available',
            'number',
            'org',
            'pacing_type',
            'partner',
            'program_types',
            'published',
            'seat_types',
            'short_description',
            'staff_uuids',
            'start',
            'subject_uuids',
            'text',
            'title',
            'transcript_languages',
            'type',
            'weeks_to_complete',
        )


class CourseRunFacetSerializer(BaseDjangoESDSLFacetSerializer):
    """
    Serializer for course run facets elasticsearch document.
    """

    class Meta:
        """
        Meta options.
        """

        ignore_fields = COMMON_IGNORED_FIELDS


class CourseRunSearchModelSerializer(
    DocumentDSLSerializerMixin, ContentTypeSerializer, CourseRunWithProgramsSerializer
):
    """
    Serializer for course run model elasticsearch document.
    """

    class Meta(CourseRunWithProgramsSerializer.Meta):
        """
        Meta options.
        """

        document = CourseRunDocument
        fields = ContentTypeSerializer.Meta.fields + CourseRunWithProgramsSerializer.Meta.fields
