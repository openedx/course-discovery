from django.conf.urls import include, url

urlpatterns = [
    url(r'^api/', include('course_discovery.apps.journal.api.urls', namespace='api')),
]
