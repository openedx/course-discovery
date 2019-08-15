"""
URLs for the admin autocomplete lookups.
"""
from django.conf.urls import url

from course_discovery.apps.core.lookups import UserAutocomplete

app_name = 'core'

urlpatterns = [
    url(r'^user-autocomplete/$', UserAutocomplete.as_view(), name='user-autocomplete',),
]
