"""
URLs for the course publisher comments views.
"""
from django.conf.urls import include, url

app_name = 'publisher_comments'

urlpatterns = [
    url(r'^api/', include('course_discovery.apps.publisher_comments.api.urls')),
]
