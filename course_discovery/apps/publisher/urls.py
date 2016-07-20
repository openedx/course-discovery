"""
URLs for the course builder views.
"""
from django.conf.urls import url

from course_discovery.apps.publisher.views import CourseAboutView

urlpatterns = [
    url(r'^course_about/$', CourseAboutView.as_view(), name='course_about'),
]
