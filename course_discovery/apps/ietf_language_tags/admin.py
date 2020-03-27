""" Admin configuration. """

from django.contrib import admin

from course_discovery.apps.ietf_language_tags.models import LanguageTag


class myModelAdmin(admin.ModelAdmin):
    def has_module_permission(self, request):
        perm = super().has_module_permission(request)
        return perm or request.user.is_staff

    def has_view_permission(self, request, obj=None):
        perm = super().has_view_permission(request, obj)
        return perm or request.user.is_staff

    def has_add_permission(self, request):
        perm = super().has_add_permission(request)
        return perm or request.user.is_staff

    def has_change_permission(self, request, obj=None):
        perm = super().has_change_permission(request, obj)
        return perm or request.user.is_staff

    def has_delete_permission(self, request, obj=None):
        perm = super().has_delete_permission(request, obj)
        return perm or request.user.is_staff


@admin.register(LanguageTag)
class LanguageTagAdmin(myModelAdmin):
    list_display = ('code', 'name',)
    ordering = ('code', 'name',)
    search_fields = ('code', 'name',)
