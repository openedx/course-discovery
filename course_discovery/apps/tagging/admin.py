from django.conf import settings
from django.contrib import admin
from django.core.exceptions import PermissionDenied

from course_discovery.apps.course_metadata.models import Course
from course_discovery.apps.tagging.models import CourseVertical, SubVertical, Vertical


@admin.register(Vertical)
class VerticalAdmin(admin.ModelAdmin):
    """
    Admin class for Vertical model.
    """
    list_display = ('name', 'is_active', 'slug',)
    search_fields = ('name',)

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            raise PermissionDenied("You are not authorized to perform this action.")
        super().save_model(request, obj, form, change)


@admin.register(SubVertical)
class SubVerticalAdmin(admin.ModelAdmin):
    """
    Admin class for SubVertical model.
    """
    list_display = ('name', 'is_active', 'slug', 'verticals')
    list_filter = ('verticals', )
    search_fields = ('name',)
    ordering = ('name',)

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            raise PermissionDenied("You are not authorized to perform this action.")
        super().save_model(request, obj, form, change)


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

    def save_model(self, request, obj, form, change):
        allowed_groups = getattr(settings, 'VERTICALS_MANAGEMENT_GROUPS', [])
        if not (request.user.is_superuser or request.user.groups.filter(name__in=allowed_groups).exists()):
            raise PermissionDenied("You are not authorized to perform this action.")
        super().save_model(request, obj, form, change)