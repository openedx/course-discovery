""" Publisher API URLs. """
from django.conf.urls import url

from course_discovery.apps.publisher.api.views import CourseRoleAssignmentView

urlpatterns = [
    url(
        r'^course_role_assignments/(?P<pk>\d+)/$', CourseRoleAssignmentView.as_view(), name='course_role_assignments'
    ),
]
