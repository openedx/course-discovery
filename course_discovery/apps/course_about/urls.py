"""
URLs for the course about views.
"""
from django.conf.urls import url
from course_discovery.apps.course_about.views import CourseListing

urlpatterns = [
    url(r'^listing/$', CourseListing.as_view(), name='courses_list'),
]
