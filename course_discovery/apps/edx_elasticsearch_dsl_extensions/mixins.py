from functools import partial


class CatalogDataFilterBackendMixin:
    """
    Catalog data filter backend mixin.
    """

    def filter_queryset(self, request, queryset, view):
        """
        Filter the queryset.

        Return data for the default partner, if no partner is requested

        :param request: Django REST framework request.
        :param queryset: Base queryset.
        :param view: View.
        :type request: rest_framework.request.Request
        :type queryset: elasticsearch_dsl.search.Search
        :type view: rest_framework.viewsets.ReadOnlyModelViewSet
        :return: Updated queryset.
        :rtype: elasticsearch_dsl.search.Search
        """
        if not self.is_partner_requested(request, view) and request.method == 'GET':
            queryset = self.apply_filter_term(
                queryset,
                {'field': 'partner'},
                request.site.partner.short_code
            )

        return super().filter_queryset(request, queryset, view)

    def is_partner_requested(self, request, view):
        return 'partner' in self.get_filter_query_params(request, view)


class FieldActionFilterBackendMinix:
    """
    Field action filter backend minix.
    """

    @staticmethod
    def split_field_action(field):
        *_, field_action = field.rpartition('.')
        return field_action

    @staticmethod
    def dispatch_field_action(action, value):
        return {
            'lower': lambda: str(value).lower(),
        }.get(action, lambda: value)()

    def get_filter_query_params(self, request, view):
        """
        Overrides the default behavior of the method
        to be able to apply actions under values defined into field name.
        """
        filter_query_params = super().get_filter_query_params(request, view)
        for key, options in filter_query_params.items():
            action = self.split_field_action(options['field'])
            dispatch_action = partial(self.dispatch_field_action, action)
            options['values'] = list(map(dispatch_action, options['values']))

        return filter_query_params
