from django.contrib import admin

from course_discovery.apps.core.models import Catalog


@admin.register(Catalog)
class CatalogAdmin(admin.ModelAdmin):
    list_display = ('name',)
    readonly_fields = ('created', 'modified',)

    class Media(object):
        js = ('js/catalogs-change-form.js',)
