from django.conf.urls import include, url

app_name = 'api'

urlpatterns = [
    url(r'^v1/', include('course_discovery.apps.edx_catalog_extensions.api.v1.urls')),
]
