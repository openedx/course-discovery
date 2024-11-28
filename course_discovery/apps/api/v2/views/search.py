from course_discovery.apps.api.v1.views.search import AggregateSearchViewSet as AggregateSearchViewSetV1
from course_discovery.apps.edx_elasticsearch_dsl_extensions.search import SearchAfterSearch
from course_discovery.apps.edx_elasticsearch_dsl_extensions.viewsets import CustomSearchAfterPagination


class AggregateSearchViewSet(AggregateSearchViewSetV1):
    pagination_class = CustomSearchAfterPagination
    ordering_fields = {"start": "start", "aggregation_uuid": "aggregation_uuid"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.search = SearchAfterSearch(using=self.client, index=self.index, doc_type=self.document._doc_type.name)
