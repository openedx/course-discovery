from django.conf.urls import url

from course_discovery.apps.edx_catalog_extensions.views import DistinctCountsAggregateSearchViewSet

distinct_facets = DistinctCountsAggregateSearchViewSet.as_view({'get': 'facets'})

urlpatterns = [
    url(r'^v1/search/all/facets', distinct_facets, name='edx-search-all-facets')
]
