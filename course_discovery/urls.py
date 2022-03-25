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

from auth_backends.urls import oauth2_urlpatterns
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.utils.translation import gettext_lazy as _
from django.views.i18n import JavaScriptCatalog
from drf_yasg.views import get_schema_view
from edx_api_doc_tools import make_api_info
from rest_framework import permissions

from course_discovery.apps.core import views as core_views
from course_discovery.apps.course_metadata.views import QueryPreviewView

admin.site.site_header = _('Discovery Service Administration')
admin.site.site_title = admin.site.site_header
admin.autodiscover()

api_info = make_api_info(title="Discovery API", version="v1")
schema_view = get_schema_view(
    api_info,
    public=False,
    permission_classes=(permissions.IsAuthenticated,),
)

urlpatterns = oauth2_urlpatterns + [
    path('admin/course_metadata/', include('course_discovery.apps.course_metadata.urls', namespace='admin_metadata')),
    path('admin/', admin.site.urls),
    path('api/', include('course_discovery.apps.api.urls', namespace='api')),
    # Use the same auth views for all logins, including those originating from the browseable API.
    path('api-auth/', include((oauth2_urlpatterns, 'rest_framework'))),
    path('api-docs/', schema_view.with_ui('swagger', cache_timeout=0), name='api_docs'),
    path('auto_auth/', core_views.AutoAuth.as_view(), name='auto_auth'),
    path('health/', core_views.health, name='health'),
    path('', QueryPreviewView.as_view()),
    path('publisher/', include('course_discovery.apps.publisher.urls', namespace='publisher')),
    path('language-tags/', include('course_discovery.apps.ietf_language_tags.urls', namespace='language_tags')),
    path('taxonomy/', include('course_discovery.apps.taxonomy_support.urls', namespace='taxonomy_support')),
    path('comments/', include('django_comments.urls')),
    path('i18n/', include('django.conf.urls.i18n')),
    path('jsi18n/', JavaScriptCatalog.as_view(), name='javascript-catalog'),
    path('taggit_autosuggest/', include('taggit_autosuggest.urls')),
    path('api/', include('course_discovery.apps.learner_pathway.api.urls', namespace='learner_pathway_api')),
]

# edx-drf-extensions csrf app
urlpatterns += [
    path('', include('csrf.urls')),
]

# Add the catalog extension urls if edx_catalog_extensions is installed.
if 'course_discovery.apps.edx_catalog_extensions' in settings.INSTALLED_APPS:
    urlpatterns.append(
        path('extensions/', include('course_discovery.apps.edx_catalog_extensions.urls', namespace='extensions'))
    )

if settings.DEBUG:  # pragma: no cover
    # We need this url pattern to serve user uploaded assets according to
    # https://docs.djangoproject.com/en/1.11/howto/static-files/#serving-files-uploaded-by-a-user-during-development
    # This was modified to use LOCAL_MEDIA_URL to be able to server static files to external services like edx-mktg
    urlpatterns += static(settings.LOCAL_DISCOVERY_MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # If using gunicorn instead of runserver in development, also need to explicitly serve static files
    if settings.STATIC_SERVE_EXPLICITLY:
        urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    if os.environ.get('ENABLE_DJANGO_TOOLBAR', False):
        import debug_toolbar

        urlpatterns.append(path('__debug__/', include(debug_toolbar.urls)))
