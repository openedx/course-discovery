from django.contrib import admin
from guardian.admin import GuardedModelAdmin

from course_discovery.apps.catalogs.models import Catalog


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


@admin.register(Catalog)
class CatalogAdmin(GuardedModelAdmin, myModelAdmin):
    list_display = ('name',)
    readonly_fields = ('created', 'modified',)

    class Media:
        js = ('js/catalogs-change-form.js',)
