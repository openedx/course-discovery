from django.conf.urls import include
from django.urls import path

app_name = 'catalog_extensions'

urlpatterns = [
    path('api/', include('course_discovery.apps.edx_catalog_extensions.api.urls')),
]
