"""
URLs for the course publisher comments views.
"""
from django.conf.urls import include, url


urlpatterns = [
    url(r'^api/', include('course_discovery.apps.publisher_comments.api.urls', namespace='api')),
]
