""" This module contains the admin classes for the tagging app models """
from django.conf import settings
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from simple_history.admin import SimpleHistoryAdmin

from course_discovery.apps.tagging.models import CourseVertical, SubVertical, UpdateCourseVerticalsConfig, Vertical


class SubVerticalInline(admin.TabularInline):
    """
    Inline form for SubVertical under VerticalAdmin.
    """
    model = SubVertical
    extra = 0
    fields = ('name', 'is_active', 'slug')
    readonly_fields = ('slug',)
    show_change_link = True


@admin.register(Vertical)
class VerticalAdmin(SimpleHistoryAdmin):
    """
    Admin class for Vertical model.
    """
    list_display = ('name', 'is_active', 'slug',)
    search_fields = ('name',)
    inlines = [SubVerticalInline]

    def save_model(self, request, obj, form, change):
        """
        Override the save_model method to restrict non-superuser from saving the model
        """
        if not request.user.is_superuser:
            raise PermissionDenied("You are not authorized to perform this action.")
        super().save_model(request, obj, form, change)


@admin.register(SubVertical)
class SubVerticalAdmin(SimpleHistoryAdmin):
    """
    Admin class for SubVertical model.
    """
    list_display = ('name', 'is_active', 'slug', 'vertical')
    list_filter = ('vertical', )
    search_fields = ('name',)
    ordering = ('name',)

    def save_model(self, request, obj, form, change):
        """
        Override the save_model method to restrict non-superuser from saving the model
        """
        if not request.user.is_superuser:
            raise PermissionDenied("You are not authorized to perform this action.")
        super().save_model(request, obj, form, change)


@admin.register(CourseVertical)
class CourseVerticalAdmin(SimpleHistoryAdmin):
    """
    Admin class for CourseVertical model.
    """
    list_display = ('course', 'vertical', 'sub_vertical')
    list_filter = ('vertical', 'sub_vertical')
    search_fields = ('course__title', 'vertical__name', 'sub_vertical__name')
    ordering = ('course__title',)
    autocomplete_fields = ('course',)

    def get_queryset(self, request):
        """
        Override the get_queryset method to select related fields and resolve N+1 queries.
        """
        return super().get_queryset(request).select_related('course', 'vertical', 'sub_vertical')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """
        Override the formfield_for_foreignkey method to filter non-draft entry of courses and active vertical and
        sub-vertical filters.
        """
        if db_field.name == 'vertical':
            kwargs['queryset'] = Vertical.objects.filter(is_active=True)
        elif db_field.name == 'sub_vertical':
            kwargs['queryset'] = SubVertical.objects.filter(is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        """
        Override the save_model method to allow only superuser and users in allowed groups to save the model.
        """
        allowed_groups = getattr(settings, 'VERTICALS_MANAGEMENT_GROUPS', [])
        if not (request.user.is_superuser or request.user.groups.filter(name__in=allowed_groups).exists()):
            raise PermissionDenied("You are not authorized to perform this action.")
        super().save_model(request, obj, form, change)


@admin.register(UpdateCourseVerticalsConfig)
class UpdateCourseVerticalsConfigurationAdmin(admin.ModelAdmin):
    """
    Admin for ArchiveCoursesConfig model.
    """
    list_display = ('id', 'enabled', 'changed_by', 'change_date')
