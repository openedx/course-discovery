"""
Serve admin and API urls
"""
from django.conf.urls import patterns, url, include
from django.contrib import admin
from course_discovery.settings.utils import stub_user_info_response

urlpatterns = patterns(
    '',
    url(r'^admin/', include(admin.site.urls)),
    url(r'^api/', include('course_discovery.apps.api.urls', namespace='api')),
    url(r'^user_info/', stub_user_info_response)
)
