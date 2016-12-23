""" Publisher API URLs. """
from django.conf.urls import url

from course_discovery.apps.publisher.api.views import CourseRoleAssignmentView, OrganizationGroupUserView

urlpatterns = [
    url(r'^course_role_assignments/(?P<pk>\d+)/$', CourseRoleAssignmentView.as_view(), name='course_role_assignments'),
    url(r'^admins/organizations/(?P<pk>\d+)/users/$', OrganizationGroupUserView.as_view(),
        name='organization_group_users'),
]
