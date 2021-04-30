from django.conf.urls import include, url

from edly_discovery_app.api.v1 import views


app_name = 'v1'
urlpatterns = [
    url(r'^edly_sites/', views.EdlySiteViewSet.as_view(), name='edly_sites'),
]
