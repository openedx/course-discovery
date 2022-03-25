"""
Root API URLs.

All API URLs should be versioned, so urlpatterns should only
contain namespaces for the active versions of the API.
"""
from django.conf.urls import include
from django.urls import path

app_name = 'learner_pathway'

urlpatterns = [
    path('v1/', include('course_discovery.apps.learner_pathway.api.v1.urls')),
]
