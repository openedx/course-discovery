"""
URLs for the course publisher views.
"""
from django.conf.urls import url

from course_discovery.apps.publisher.views import CreateCourseView, UpdateCourseView

urlpatterns = [
    url(r'^course_about/$', CreateCourseView.as_view(), name='course_about'),
    url(r'^course_about/edit/(?P<pk>\d+)/$', UpdateCourseView.as_view(), name='edit_course'),
]
