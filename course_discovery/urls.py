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
from django.conf.urls.static import static
from django.contrib import admin
from django.views.i18n import javascript_catalog

from course_discovery.apps.api.views import SwaggerSchemaView
from course_discovery.apps.core import views as core_views
from course_discovery.apps.course_metadata.views import QueryPreviewView


admin.autodiscover()

urlpatterns = auth_urlpatterns + [
    url(r'^admin/course_metadata/', include('course_discovery.apps.course_metadata.urls', namespace='admin_metadata')),
    url(r'^admin/core/', include('course_discovery.apps.core.urls', namespace='admin_core')),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^api/', include('course_discovery.apps.api.urls', namespace='api')),
    # Use the same auth views for all logins, including those originating from the browseable API.
    url(r'^api-auth/', include(auth_urlpatterns, namespace='rest_framework')),
    url(r'^api-docs/', SwaggerSchemaView.as_view(), name='api_docs'),
    url(r'^auto_auth/$', core_views.AutoAuth.as_view(), name='auto_auth'),
    url(r'^health/$', core_views.health, name='health'),
    url('^$', QueryPreviewView.as_view()),
    url(r'^publisher/', include('course_discovery.apps.publisher.urls', namespace='publisher')),
    url(
        r'^publisher/comments/', include(
            'course_discovery.apps.publisher_comments.urls', namespace='publisher_comments'
        )
    ),
    url(r'^language-tags/', include('course_discovery.apps.ietf_language_tags.urls', namespace='language_tags')),
    url(r'^comments/', include('django_comments.urls')),
    url(r'^i18n/', include('django.conf.urls.i18n')),
    url(r'^jsi18n/$', javascript_catalog, name='javascript-catalog'),
    url(r'^taggit_autosuggest/', include('taggit_autosuggest.urls')),
]

# Add the catalog extension urls if edx_catalog_extensions is installed.
if 'course_discovery.apps.edx_catalog_extensions' in settings.INSTALLED_APPS:
    urlpatterns.append(
        url(r'^extensions/', include('course_discovery.apps.edx_catalog_extensions.urls', namespace='extensions'))
    )

if settings.DEBUG:  # pragma: no cover
    # We need this url pattern to serve user uploaded assets according to
    # https://docs.djangoproject.com/en/1.10/howto/static-files/#serving-files-uploaded-by-a-user-during-development
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    if os.environ.get('ENABLE_DJANGO_TOOLBAR', False):
        import debug_toolbar  # pylint: disable=wrong-import-order,wrong-import-position,import-error

        urlpatterns.append(url(r'^__debug__/', include(debug_toolbar.urls)))
