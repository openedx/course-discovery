from django.conf.urls import include
from django.urls import path

app_name = 'publisher'

urlpatterns = [
    path('api/', include('course_discovery.apps.publisher.api.urls')),
]
