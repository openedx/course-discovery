import datetime

import pytz
from django_elasticsearch_dsl_drf.serializers import DocumentSerializer
from rest_framework import serializers
from taxonomy.choices import ProductTypes
from taxonomy.utils import get_whitelisted_product_skills, get_whitelisted_serialized_skills

from course_discovery.apps.api import serializers as cd_serializers
from course_discovery.apps.api.serializers import ContentTypeSerializer, CourseWithProgramsSerializer
from course_discovery.apps.course_metadata.utils import get_course_run_estimated_hours
from course_discovery.apps.edx_elasticsearch_dsl_extensions.serializers import BaseDjangoESDSLFacetSerializer

from ..constants import BASE_SEARCH_INDEX_FIELDS, COMMON_IGNORED_FIELDS
from ..documents import CourseDocument
from .common import DateTimeSerializerMixin, DocumentDSLSerializerMixin, ModelObjectDocumentSerializerMixin

__all__ = ('CourseSearchDocumentSerializer',)


class CourseSearchDocumentSerializer(ModelObjectDocumentSerializerMixin, DateTimeSerializerMixin, DocumentSerializer):
    """
    Serializer for course elasticsearch document.
    """

    course_runs = serializers.SerializerMethodField()
    seat_types = serializers.SerializerMethodField()
    skill_names = serializers.SerializerMethodField()
    skills = serializers.SerializerMethodField()
    end_date = serializers.SerializerMethodField()
    course_ends = serializers.SerializerMethodField()

    def course_run_detail(self, request, detail_fields, course_run):
        course_run_detail = {
            'key': course_run.key,
            'enrollment_start': self.handle_datetime_field(course_run.enrollment_start),
            'enrollment_end': self.handle_datetime_field(course_run.enrollment_end),
            'go_live_date': course_run.go_live_date,
            'start': self.handle_datetime_field(course_run.start),
            'end': self.handle_datetime_field(course_run.end),
            'modified': self.handle_datetime_field(course_run.modified),
            'availability': course_run.availability,
            'status': course_run.status,
            'pacing_type': course_run.pacing_type,
            'enrollment_mode': course_run.type_legacy,
            'min_effort': course_run.min_effort,
            'max_effort': course_run.max_effort,
            'weeks_to_complete': course_run.weeks_to_complete,
            'estimated_hours': get_course_run_estimated_hours(course_run),
            'first_enrollable_paid_seat_price': course_run.first_enrollable_paid_seat_price or 0.0,
            'is_enrollable': course_run.is_enrollable,
        }
        if detail_fields:
            course_run_detail.update(
                {
                    'staff': cd_serializers.MinimalPersonSerializer(
                        course_run.staff, many=True, context={'request': request}
                    ).data,
                    'content_language': course_run.language.code if course_run.language else None,
                }
            )
        return course_run_detail

    def get_course_runs(self, result):
        request = self.context['request']
        course_runs = result.object.course_runs.all()
        now = datetime.datetime.now(pytz.UTC)
        exclude_expired = request.GET.get('exclude_expired_course_run')
        detail_fields = request.GET.get('detail_fields')
        query_params = dict(request.query_params)
        if request.method == 'POST':
            exclude_expired = request.POST.get('exclude_expired_course_run') or exclude_expired
            detail_fields = request.POST.get('detail_fields') or detail_fields

        def should_include_course_run(course_run, params, exclude_expired):
            matches_parameter = False
            for key, values in params.items():
                if hasattr(course_run, key):
                    for value in values:
                        if value == getattr(course_run, key):
                            matches_parameter = True
                if matches_parameter:
                    break
            return (not exclude_expired or matches_parameter or course_run.end is None or course_run.end > now)

        return [
            self.course_run_detail(request, detail_fields, course_run)
            for course_run in course_runs
            # Check if exclude_expire_course_run is in query_params then exclude the course
            # runs whose end date is passed. We do this here, rather than as an additional
            # `.exclude` because the course_runs have been prefetched by the read_queryset
            # of the search index.
            if should_include_course_run(course_run, query_params, exclude_expired)
        ]

    def get_seat_types(self, result):
        seat_types = [seat.slug for course_run in result.object.course_runs.all() for seat in course_run.seat_types]
        return list(set(seat_types))

    def get_skill_names(self, result):
        course_skills = get_whitelisted_product_skills(result.key, product_type=ProductTypes.Course)
        return list(set(course_skill.skill.name for course_skill in course_skills))

    def get_skills(self, result):
        return get_whitelisted_serialized_skills(result.key, product_type=ProductTypes.Course)

    def get_end_date(self, result):
        return self.handle_datetime_field(result.end_date)

    def get_course_ends(self, result):
        return str(result.course_ends)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context['request']
        detail_fields = request.GET.get('detail_fields')
        # if detail_fields query_param not in request than do not add the following fields in serializer response.
        if not detail_fields:
            self.fields.pop('level_type', None)
            self.fields.pop('modified', None)
            self.fields.pop('outcome', None)

    def to_representation(self, instance):
        _object = self.get_model_object_by_instance(instance)
        setattr(instance, 'object', _object)  # pylint: disable=literal-used-as-attribute
        return super().to_representation(instance)

    class Meta:
        """
        Meta options.
        """

        document = CourseDocument
        ignore_fields = COMMON_IGNORED_FIELDS
        fields = BASE_SEARCH_INDEX_FIELDS + (
            'full_description',
            'key',
            'short_description',
            'title',
            'card_image_url',
            'image_url',
            'course_runs',
            'uuid',
            'seat_types',
            'skill_names',
            'skills',
            'end_date',
            'course_ends',
            'subjects',
            'languages',
            'organizations',
            'outcome',
            'level_type',
            'modified',
            'course_type',
            'course_length',
            'enterprise_subscription_inclusion',
            'external_course_marketing_type',
            'product_source',
        )


# pylint: disable=abstract-method
class CourseFacetSerializer(BaseDjangoESDSLFacetSerializer):
    """
    Serializer for course facets elasticsearch document.
    """

    class Meta:
        ignore_fields = COMMON_IGNORED_FIELDS


class CourseSearchModelSerializer(DocumentDSLSerializerMixin, ContentTypeSerializer, CourseWithProgramsSerializer):
    """
    Serializer for course model elasticsearch document.
    """

    class Meta(CourseWithProgramsSerializer.Meta):
        document = CourseDocument
        fields = ContentTypeSerializer.Meta.fields + CourseWithProgramsSerializer.Meta.fields
