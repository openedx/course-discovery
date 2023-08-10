from django.contrib import admin
from guardian.admin import GuardedModelAdmin

from course_discovery.apps.catalogs.models import Catalog


@admin.register(Catalog)
class CatalogAdmin(GuardedModelAdmin):
    list_display = ('id', 'name',)
    readonly_fields = ('created', 'modified',)
    search_fields = ('id', 'name')

    class Media:
        js = ('js/catalogs-change-form.js',)
