from django.conf.urls import url

from course_discovery.apps.edx_catalog_extensions.api.v1.views import DistinctCountsAggregateSearchViewSet, get_fixture

# Only expose the facets action of this view
distinct_facets_action = DistinctCountsAggregateSearchViewSet.as_view({'get': 'facets'})

urlpatterns = [
    url(r'^search/all/facets', distinct_facets_action, name='search-all-facets'),
    url(r'^fixture/', get_fixture, name='get-fixture')
]
