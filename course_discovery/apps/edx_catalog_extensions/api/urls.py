from django.conf.urls import url

from course_discovery.apps.edx_catalog_extensions.api.views import DistinctCountsAggregateSearchViewSet

distinct_facets_action = DistinctCountsAggregateSearchViewSet.as_view({'get': 'facets'})

urlpatterns = [
    url(r'^search_all', distinct_facets_action, name='extensions-search-all')
]
