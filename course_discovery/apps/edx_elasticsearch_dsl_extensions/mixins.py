from functools import partial

from course_discovery.apps.edx_elasticsearch_dsl_extensions.constants import LOOKUP_FILTER_MATCH


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


class MatchFilterBackendMixin:
    """
    Match filter backend minix.
    """

    @classmethod
    def apply_filter_term(cls, queryset, options, value):
        if options.get('lookup') in (LOOKUP_FILTER_MATCH,):
            return queryset
        return super().apply_filter_term(queryset, options, value)

    @classmethod
    def apply_filter_match(cls, queryset, options, value):
        return cls.apply_filter(
            queryset=queryset,
            options=options,
            args=['match'],
            kwargs={options['field']: value}
        )

    def filter_queryset(self, request, queryset, view):
        filter_query_params = self.get_filter_query_params(request, view)
        for options in filter_query_params.values():
            if options['lookup']:
                for value in options['values']:
                    if options['lookup'] == LOOKUP_FILTER_MATCH:
                        queryset = self.apply_filter_match(queryset, options, value)
        return super().filter_queryset(request, queryset, view)


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
        filter_query_params = super().get_filter_query_params(request, view)  # pylint: disable=no-member
        for __, options in filter_query_params.items():
            action = self.split_field_action(options['field'])
            dispatch_action = partial(self.dispatch_field_action, action)
            options['values'] = list(map(dispatch_action, options['values']))

        return filter_query_params
