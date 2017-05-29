import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import QuerySet
from django.utils.translation import ugettext as _
from django_filters import rest_framework as filters
from drf_haystack.filters import HaystackFilter as DefaultHaystackFilter
from drf_haystack.filters import HaystackFacetFilter
from drf_haystack.query import FacetQueryBuilder
from dry_rest_permissions.generics import DRYPermissionFiltersBase
from guardian.shortcuts import get_objects_for_user
from rest_framework.exceptions import NotFound, PermissionDenied

from course_discovery.apps.api.utils import cast2int
from course_discovery.apps.core.models import Partner
from course_discovery.apps.course_metadata.choices import ProgramStatus
from course_discovery.apps.course_metadata.models import Course, CourseRun, Organization, Program

logger = logging.getLogger(__name__)
User = get_user_model()


class PermissionsFilter(DRYPermissionFiltersBase):
    def filter_list_queryset(self, request, queryset, view):
        """ Filters the list queryset, returning only the objects accessible by the user.

        If a username parameter is passed on the querystring, the filter will will return objects accessible by
        the user corresponding to the given username. NOTE: This functionality is only accessible to staff users.

        Raises:
            PermissionDenied -- If a username querystring parameter is specified, but the user is not a staff user.
            Http404 -- If no User corresponding to the given username exists.

        Returns:
            QuerySet
        """
        perm = queryset.model.get_permission('view')
        user = request.user
        username = request.query_params.get('username', None)

        if username:
            if request.user.is_staff:
                try:
                    user = User.objects.get(username=username)
                except User.DoesNotExist:
                    raise NotFound(_('No user with the username [{username}] exists.').format(username=username))

            else:
                raise PermissionDenied(
                    _('Only staff users are permitted to filter by username. Remove the username parameter.')
                )

        return get_objects_for_user(user, perm)


class FacetQueryBuilderWithQueries(FacetQueryBuilder):
    def build_query(self, **query_filters):
        query = super(FacetQueryBuilderWithQueries, self).build_query(**query_filters)
        facet_serializer_cls = self.view.get_facet_serializer_class()
        query['query_facets'] = getattr(facet_serializer_cls.Meta, 'field_queries', {})
        return query


class HaystackRequestFilterMixin:
    @staticmethod
    def get_request_filters(request):
        filters = HaystackFacetFilter.get_request_filters(request)

        # Remove items with empty values.
        #
        # NOTE 1: We copy the keys list to avoid a RuntimeError that occurs when modifying a dict while iterating.
        #
        # NOTE 2: We filter in this fashion, as opposed to dictionary comprehension, due to the fact that filters
        # is a `QueryDict` object, not a `dict`. Dictionary comprehension will not preserve the values of
        # `QueryDict.getlist()`. Since we support multiple values for a single parameter, dictionary comprehension is a
        # dealbreaker (and production breaker).
        for key in list(filters.keys()):
            if not filters[key]:
                del filters[key]

        return filters


class HaystackFacetFilterWithQueries(HaystackRequestFilterMixin, HaystackFacetFilter):
    query_builder_class = FacetQueryBuilderWithQueries


class HaystackFilter(HaystackRequestFilterMixin, DefaultHaystackFilter):
    @staticmethod
    def get_request_filters(request):
        filters = HaystackRequestFilterMixin.get_request_filters(request)

        # Return data for the default partner, if no partner is requested
        if not any(field in filters for field in ('partner', 'partner_exact')):
            filters['partner'] = Partner.objects.get(pk=settings.DEFAULT_PARTNER_ID).short_code

        return filters


class CharListFilter(filters.CharFilter):
    """ Filters a field via a comma-delimited list of values. """

    def filter(self, qs, value):  # pylint: disable=method-hidden
        if value not in (None, ''):
            value = value.split(',')

        return super(CharListFilter, self).filter(qs, value)


class UUIDListFilter(CharListFilter):
    """ Filters a field via a comma-delimited list of UUIDs. """

    def __init__(self, name='uuid', label=None, widget=None, method=None, lookup_expr='in', required=False,
                 distinct=False, exclude=False, **kwargs):
        super().__init__(name=name, label=label, widget=widget, method=method, lookup_expr=lookup_expr,
                         required=required, distinct=distinct, exclude=exclude, **kwargs)


class FilterSetMixin:
    def _apply_filter(self, name, queryset, value):
        return getattr(queryset, name)() if cast2int(value, name) else queryset

    def filter_active(self, queryset, name, value):
        return self._apply_filter(name, queryset, value)

    def filter_marketable(self, queryset, name, value):
        return self._apply_filter(name, queryset, value)


class CourseFilter(filters.FilterSet):
    keys = CharListFilter(name='key', lookup_expr='in')

    class Meta:
        model = Course
        fields = ['keys']


class CourseRunFilter(FilterSetMixin, filters.FilterSet):
    active = filters.BooleanFilter(method='filter_active')
    marketable = filters.BooleanFilter(method='filter_marketable')
    keys = CharListFilter(name='key', lookup_expr='in')

    @property
    def qs(self):
        # This endpoint supports query via Haystack. If that form of filtering is active,
        # do not attempt to treat the queryset as a normal Django queryset.
        if not isinstance(self.queryset, QuerySet):
            return self.queryset

        return super(CourseRunFilter, self).qs

    class Meta:
        model = CourseRun
        fields = ['keys', 'hidden']


class ProgramFilter(FilterSetMixin, filters.FilterSet):
    marketable = filters.BooleanFilter(method='filter_marketable')
    status = filters.MultipleChoiceFilter(choices=ProgramStatus.choices)
    type = filters.CharFilter(name='type__name', lookup_expr='iexact')
    types = CharListFilter(name='type__slug', lookup_expr='in')
    uuids = UUIDListFilter()

    class Meta:
        model = Program
        fields = ('hidden', 'marketable', 'status', 'type', 'types',)


class OrganizationFilter(filters.FilterSet):
    tags = CharListFilter(name='tags__name', lookup_expr='in')
    uuids = UUIDListFilter()

    class Meta:
        model = Organization
        fields = ('tags', 'uuids',)
