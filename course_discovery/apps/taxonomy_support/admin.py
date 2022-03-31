"""
Admin definitions for models defined in `taxonomy-support`.
"""
from django.contrib import admin

from course_discovery.apps.taxonomy_support.models import CourseRecommendation


@admin.register(CourseRecommendation)
class CourseRecommendationAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'course', 'recommended_course', 'skills_intersection_ratio', 'skills_intersection_length',
        'subjects_intersection_ratio', 'subjects_intersection_length',
    )
    readonly_fields = ('created', 'modified', )
    search_fields = ('id', 'course', 'recommended_course', )
