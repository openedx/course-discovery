
from django.urls import path, re_path

from course_discovery.apps.publisher.api.views import (
    OrganizationGroupUserView, OrganizationUserRoleView, OrganizationUserView
)

app_name = 'api'

urlpatterns = [
    re_path(r'^admins/organizations/(?P<pk>[0-9a-f-]+)/roles/$', OrganizationUserRoleView.as_view(),
            name='organization_user_roles'),
    re_path(r'^admins/organizations/(?P<pk>[0-9a-f-]+)/users/$', OrganizationGroupUserView.as_view(),
            name='organization_group_users'),
    path('admins/organizations/users/', OrganizationUserView.as_view(), name='organization_users'),
]
