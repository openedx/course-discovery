"""
URLs for the course publisher views.
"""
from django.conf.urls import url
from course_discovery.apps.course_metadata.constants import COURSE_RUN_ID_REGEX
from course_discovery.apps.publisher.views import UnpublishedCourseListing, CourseDetailPrepublish

urlpatterns = [
    url(r'^courses/$', UnpublishedCourseListing.as_view(), name='unpublished_courses'),
    url(
        r'^course_runs/{course_run_key}/prepublish$'.format(course_run_key=r'(.*?)'),
        CourseDetailPrepublish.as_view(),
        name='course_run_prepublish'
    ),
]
