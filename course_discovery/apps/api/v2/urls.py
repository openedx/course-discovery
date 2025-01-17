"""API v2 URLs."""

from django.urls import re_path
from rest_framework import routers

from course_discovery.apps.api.v2.views import search as search_views
from course_discovery.apps.api.v2.views.catalog_queries import CatalogQueryContainsViewSet

app_name = 'v2'

urlpatterns = [
    re_path(r'^catalog/query_contains/?', CatalogQueryContainsViewSet.as_view(), name='catalog-query_contains'),
]

router = routers.SimpleRouter()
router.register(r'search/all', search_views.AggregateSearchViewSet, basename='search-all')
urlpatterns += router.urls
