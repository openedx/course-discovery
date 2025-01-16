from django.contrib import admin

from course_discovery.apps.course_metadata.models import Course
from course_discovery.apps.tagging.models import CourseVertical, SubVertical, Vertical


@admin.register(Vertical)
class VerticalAdmin(admin.ModelAdmin):
    """
    Admin class for Vertical model.
    """
    list_display = ('name', 'is_active', 'slug',)
    search_fields = ('name',)


@admin.register(SubVertical)
class SubVerticalAdmin(admin.ModelAdmin):
    """
    Admin class for SubVertical model.
    """
    list_display = ('name', 'is_active', 'slug', 'verticals')
    list_filter = ('verticals', )
    search_fields = ('name',)
    ordering = ('name',)


@admin.register(CourseVertical)
class CourseVerticalAdmin(admin.ModelAdmin):
    """
    Admin class for CourseVertical model.
    """
    list_display = ('course', 'vertical', 'sub_vertical')
    list_filter = ('vertical', 'sub_vertical')
    search_fields = ('course__title', 'vertical__name', 'sub_vertical__name')
    ordering = ('course__title',)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """
        Override the formfield_for_foreignkey method to filter non-draft entry of courses and active vertical and
        sub-vertical filters.
        """
        if db_field.name == 'course':
            kwargs['queryset'] = Course.objects.filter(draft=False)
        elif db_field.name == 'vertical':
            kwargs['queryset'] = Vertical.objects.filter(is_active=True)
        elif db_field.name == 'sub_vertical':
            kwargs['queryset'] = SubVertical.objects.filter(is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
