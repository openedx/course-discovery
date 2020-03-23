from django.conf.urls import url

from course_discovery.apps.publisher.api.views import (
    OrganizationGroupUserView, OrganizationUserRoleView, OrganizationUserView
)

app_name = 'api'

urlpatterns = [
    url(r'^admins/organizations/(?P<pk>[0-9a-f-]+)/roles/$', OrganizationUserRoleView.as_view(),
        name='organization_user_roles'),
    url(r'^admins/organizations/(?P<pk>[0-9a-f-]+)/users/$', OrganizationGroupUserView.as_view(),
        name='organization_group_users'),
    url(r'^admins/organizations/users/$', OrganizationUserView.as_view(), name='organization_users'),
]
