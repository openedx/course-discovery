"""API v2 Search"""

from course_discovery.apps.api.v1.views.search import AggregateSearchViewSet as AggregateSearchViewSetV1
from course_discovery.apps.course_metadata.search_indexes import serializers as search_indexes_serializers
from course_discovery.apps.edx_elasticsearch_dsl_extensions.search import SearchAfterSearch
from course_discovery.apps.edx_elasticsearch_dsl_extensions.viewsets import SearchAfterPagination


class AggregateSearchViewSet(AggregateSearchViewSetV1):
    """
    Viewset for searching Elasticsearch documents using search_after pagination.

    This viewset extends the functionality of the original AggregateSearchViewSet
    by implementing search_after pagination, which allows for efficient pagination 
    through large datasets in Elasticsearch.
    """

    serializer_class = search_indexes_serializers.AggregateSearchSerializerV2
    pagination_class = SearchAfterPagination
    ordering_fields = {"start": "start", "aggregation_uuid": "aggregation_uuid"}
    ordering = ("-start", "aggregation_uuid")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.search = SearchAfterSearch(using=self.client, index=self.index, doc_type=self.document._doc_type.name)
