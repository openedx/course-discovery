from django.contrib import admin
from guardian.admin import GuardedModelAdmin

from course_discovery.apps.catalogs.models import Catalog


@admin.register(Catalog)
class CatalogAdmin(GuardedModelAdmin):
    list_display = ('name',)
    readonly_fields = ('created', 'modified',)

    class Media(object):
        js = ('js/catalogs-change-form.js',)
