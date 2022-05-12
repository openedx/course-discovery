from rest_framework import serializers
from rest_framework.serializers import ModelSerializer

from course_discovery.apps.api.fields import ImageField
from course_discovery.apps.api.serializers import MinimalOrganizationSerializer
from course_discovery.apps.taxonomy_support.models import CourseRecommendation


class CourseRecommendationsSerializer(ModelSerializer):
    """
    Course Recommendations Serializer.
    """
    key = serializers.CharField(source='recommended_course.key')
    title = serializers.CharField(source='recommended_course.title')
    owners = MinimalOrganizationSerializer(
        required=False, many=True, source='recommended_course.authoring_organizations'
    )
    card_image_url = ImageField(read_only=True, source='recommended_course.image_url')

    class Meta:
        model = CourseRecommendation
        exclude = ('course', 'recommended_course', 'created', 'modified')

    @staticmethod
    def apply_prefetch(queryset):
        return queryset.select_related(
            'recommended_course'
        ).prefetch_related(
            'recommended_course__authoring_organizations'
        )
