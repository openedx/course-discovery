from course_discovery.apps.api.v1.views.search import AggregateSearchViewSet as AggregateSearchViewSetV1
from course_discovery.apps.course_metadata.search_indexes import serializers as search_indexes_serializers
from course_discovery.apps.edx_elasticsearch_dsl_extensions.search import SearchAfterSearch
from course_discovery.apps.edx_elasticsearch_dsl_extensions.viewsets import SearchAfterPagination


class AggregateSearchViewSet(AggregateSearchViewSetV1):
    """
    Search all elasticsearch documents using search_after pagination.
    """

    serializer_class = search_indexes_serializers.AggregateSearchSerializerV2
    pagination_class = SearchAfterPagination
    ordering_fields = {"start": "start", "aggregation_uuid": "aggregation_uuid"}
    ordering = ("-start", "aggregation_uuid")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.search = SearchAfterSearch(using=self.client, index=self.index, doc_type=self.document._doc_type.name)
