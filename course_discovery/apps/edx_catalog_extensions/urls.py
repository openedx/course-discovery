from django.urls import include, path

app_name = 'catalog_extensions'

urlpatterns = [
    path('api/', include('course_discovery.apps.edx_catalog_extensions.api.urls')),
]
