""" Publisher API URLs. """
from django.conf.urls import url

from course_discovery.apps.publisher.api.views import (
    CourseRoleAssignmentView, OrganizationGroupUserView, UpdateCourseKeyView, CourseRevisionDetailView,
    ChangeCourseStateView, ChangeCourseRunStateView
)

urlpatterns = [
    url(r'^course_role_assignments/(?P<pk>\d+)/$', CourseRoleAssignmentView.as_view(), name='course_role_assignments'),
    url(r'^admins/organizations/(?P<pk>\d+)/users/$', OrganizationGroupUserView.as_view(),
        name='organization_group_users'),
    url(r'^course_state/(?P<pk>\d+)/$', ChangeCourseStateView.as_view(), name='change_course_state'),
    url(r'^course_runs/(?P<pk>\d+)/$', UpdateCourseKeyView.as_view(), name='update_course_key'),
    url(r'^course_revisions/(?P<history_id>\d+)/$', CourseRevisionDetailView.as_view(), name='course_revisions'),
    url(r'^course_run_state/(?P<pk>\d+)/$', ChangeCourseRunStateView.as_view(), name='change_course_run_state'),
]
