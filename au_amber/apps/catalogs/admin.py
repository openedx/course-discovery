from django.contrib import admin

from au_amber.apps.catalogs.models import Catalog


@admin.register(Catalog)
class CatalogAdmin(admin.ModelAdmin):
    list_display = ('name',)
    readonly_fields = ('created', 'modified',)

    class Media(object):
        js = ('js/catalogs-change-form.js',)
