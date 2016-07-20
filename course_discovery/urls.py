"""course_discovery URL Configuration
The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.8/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Add an import:  from blog import urls as blog_urls
    2. Add a URL to urlpatterns:  url(r'^blog/', include(blog_urls))
"""

import os

from auth_backends.urls import auth_urlpatterns
from django.conf import settings
from django.conf.urls import include, url
from django.contrib import admin

from course_discovery.apps.core import views as core_views
from course_discovery.apps.course_metadata.views import QueryPreviewView

admin.autodiscover()

urlpatterns = auth_urlpatterns + [
    url(r'^admin/', include(admin.site.urls)),
    url(r'^api/', include('course_discovery.apps.api.urls', namespace='api')),
    # Use the same auth views for all logins, including those originating from the browseable API.
    url(r'^api-auth/', include(auth_urlpatterns, namespace='rest_framework')),
    url(r'^api-docs/', include('rest_framework_swagger.urls')),
    url(r'^auto_auth/$', core_views.AutoAuth.as_view(), name='auto_auth'),
    url(r'^health/$', core_views.health, name='health'),
    url('^$', QueryPreviewView.as_view()),
    url(r'^publisher/', include('course_discovery.apps.publisher.urls', namespace='publisher')),
]

if settings.DEBUG and os.environ.get('ENABLE_DJANGO_TOOLBAR', False):  # pragma: no cover
    import debug_toolbar  # pylint: disable=wrong-import-order,wrong-import-position,import-error

    urlpatterns.append(url(r'^__debug__/', include(debug_toolbar.urls)))
