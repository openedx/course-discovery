from django.conf.urls import include
from django.urls import path

app_name = 'api'

urlpatterns = [
    path('v1/', include('course_discovery.apps.edx_catalog_extensions.api.v1.urls')),
]
