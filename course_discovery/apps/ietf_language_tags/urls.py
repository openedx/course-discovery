"""
URLs for autocomplete lookups.
"""
from django.conf.urls import url

from course_discovery.apps.ietf_language_tags.lookups import LanguageTagAutocomplete

urlpatterns = [
    url(r'^language-tag-autocomplete/$', LanguageTagAutocomplete.as_view(), name='language-tag-autocomplete',),
]
