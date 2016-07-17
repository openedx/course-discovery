"""
URLs for the course publisher views.
"""
from django.conf.urls import url
from course_discovery.apps.publisher.views import UnpublishedCourseListing

urlpatterns = [
    url(r'^courses/$', UnpublishedCourseListing.as_view(), name='unpublished_courses'),
]
