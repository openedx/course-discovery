from django.conf.urls import include, url

app_name = 'edly_discovery_app'

urlpatterns = [
    url(r'^v1/', include('course_discovery.apps.edly_discovery_app.api.v1.urls')),
]
