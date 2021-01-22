""" Admin configuration. """

from django.contrib import admin
from parler.admin import TranslatableAdmin

from course_discovery.apps.ietf_language_tags.models import LanguageTag


@admin.register(LanguageTag)
class LanguageTagAdmin(TranslatableAdmin):
    list_display = ('code', 'name',)
    ordering = ('code', 'name',)
    search_fields = ('code', 'name',)
    fields = ('code', 'name', 'name_t')
