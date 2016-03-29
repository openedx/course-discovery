""" Admin configuration. """

from django.contrib import admin

from course_discovery.apps.ietf_language_tags.models import LanguageTag


@admin.register(LanguageTag)
class LanguageTagAdmin(admin.ModelAdmin):
    list_display = ('code', 'name',)
    ordering = ('code', 'name',)
    search_fields = ('code', 'name',)
