from django.urls import include, path

app_name = 'publisher'

urlpatterns = [
    path('api/', include('course_discovery.apps.publisher.api.urls')),
]
