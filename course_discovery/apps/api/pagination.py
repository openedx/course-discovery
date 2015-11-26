from rest_framework.pagination import LimitOffsetPagination


class ElasticsearchLimitOffsetPagination(LimitOffsetPagination):
    def paginate_queryset(self, queryset, request, view=None):
        """
        Convert a paginated Elasticsearch response to a response suitable for DRF.

        Args:
            queryset (dict): Elasticsearch response
            request (Request): HTTP request

        Returns:
            List of data.
        """
        # pylint: disable=attribute-defined-outside-init
        self.limit = self.get_limit(request)
        self.offset = self.get_offset(request)
        self.count = queryset['total']
        self.request = request

        if self.count > self.limit and self.template is not None:
            self.display_page_controls = True

        return queryset['results']
