from django.conf.urls import include, url

urlpatterns = [
    url(r'^api/', include('course_discovery.apps.edx_catalog_extensions.api.urls', namespace='api')),
]
