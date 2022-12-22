from django.conf.urls import url

from edly_discovery_app.api.v1.views import dataloader_api, edly_sites


app_name = 'v1'
urlpatterns = [
    url(r'^edly_sites/', edly_sites.EdlySiteViewSet.as_view(), name='edly_sites'),
    url(r'^dataloader/', dataloader_api.EdlyDataLoaderView.as_view(), name='edly_dataloader'),
]
