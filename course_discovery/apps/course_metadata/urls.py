"""
URLs for the admin autocomplete lookups.
"""
from django.conf.urls import url

from course_discovery.apps.course_metadata.views import CourseRunSelectionAdmin


urlpatterns = [
    url(r'^update_course_runs/(?P<pk>\d+)/$', CourseRunSelectionAdmin.as_view(), name='update_course_runs',),
]
