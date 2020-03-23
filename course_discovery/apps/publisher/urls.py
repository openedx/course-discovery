from django.conf.urls import include, url

app_name = 'publisher'

urlpatterns = [
    url(r'^api/', include('course_discovery.apps.publisher.api.urls')),
]
