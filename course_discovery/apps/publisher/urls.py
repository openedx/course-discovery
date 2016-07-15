"""
URLs for the course builder views.
"""
from django.conf.urls import url
from course_discovery.apps.publisher.views import CourseListing

urlpatterns = [
    url(r'^unpublished_courses/$', CourseListing.as_view(), name='unpublished_courses'),
]
