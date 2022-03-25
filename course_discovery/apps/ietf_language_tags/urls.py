"""
URLs for autocomplete lookups.
"""

from django.urls import path

from course_discovery.apps.ietf_language_tags.lookups import LanguageTagAutocomplete

app_name = 'language_tags'

urlpatterns = [
    path('language-tag-autocomplete/', LanguageTagAutocomplete.as_view(), name='language-tag-autocomplete',),
]
