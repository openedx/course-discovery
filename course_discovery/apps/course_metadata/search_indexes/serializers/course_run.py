from django_elasticsearch_dsl_drf.serializers import DocumentSerializer
from rest_framework import serializers
from taxonomy.utils import get_course_jobs, get_whitelisted_course_skills, get_whitelisted_serialized_skills

from course_discovery.apps.api.serializers import ContentTypeSerializer, CourseRunWithProgramsSerializer
from course_discovery.apps.edx_elasticsearch_dsl_extensions.serializers import BaseDjangoESDSLFacetSerializer

from ..constants import BASE_SEARCH_INDEX_FIELDS, COMMON_IGNORED_FIELDS
from ..documents import CourseRunDocument
from .common import DateTimeSerializerMixin, DocumentDSLSerializerMixin

__all__ = ('CourseRunSearchDocumentSerializer',)


class CourseRunSearchDocumentSerializer(DateTimeSerializerMixin, DocumentSerializer):
    """
    Serializer for course run elasticsearch document.
    """

    start = serializers.SerializerMethodField()
    end = serializers.SerializerMethodField()
    enrollment_start = serializers.SerializerMethodField()
    enrollment_end = serializers.SerializerMethodField()
    skill_names = serializers.SerializerMethodField()
    skills = serializers.SerializerMethodField()
    jobs = serializers.SerializerMethodField()

    def get_start(self, obj):
        return self.handle_datetime_field(obj.start)

    def get_end(self, obj):
        return self.handle_datetime_field(obj.end)

    def get_enrollment_start(self, obj):
        return self.handle_datetime_field(obj.enrollment_start)

    def get_enrollment_end(self, obj):
        return self.handle_datetime_field(obj.enrollment_end)

    def get_skill_names(self, result):
        course_skills = get_whitelisted_course_skills(result.course_key)
        return list(set(course_skill.skill.name for course_skill in course_skills))

    def get_skills(self, result):
        return get_whitelisted_serialized_skills(result.course_key)

    def get_jobs(self, result):
        return get_course_jobs(result.key)

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
            'skill_names',
            'skills',
            'jobs',
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


# pylint: disable=abstract-method
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
