from django.conf.urls import url

from course_discovery.apps.edx_catalog_extensions.api.v1.views import (
    DistinctCountsAggregateSearchViewSet, ProgramFixtureView
)

# Only expose the facets action of this view
distinct_facets_action = DistinctCountsAggregateSearchViewSet.as_view({'get': 'facets'})

app_name = 'v1'

urlpatterns = [
    url(r'^search/all/facets', distinct_facets_action, name='search-all-facets'),
    url(r'^program-fixture/$', ProgramFixtureView.as_view(), name='get-program-fixture'),
]
