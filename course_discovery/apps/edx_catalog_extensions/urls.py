from django.conf.urls import include, url

app_name = 'catalog_extensions'

urlpatterns = [
    url(r'^api/', include('course_discovery.apps.edx_catalog_extensions.api.urls')),
]
