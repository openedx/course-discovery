import logging

import django_filters
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import QuerySet
from django.utils.translation import ugettext as _
from drf_haystack.filters import HaystackFacetFilter, HaystackFilter as DefaultHaystackFilter
from drf_haystack.query import FacetQueryBuilder
from dry_rest_permissions.generics import DRYPermissionFiltersBase
from guardian.shortcuts import get_objects_for_user
from rest_framework.exceptions import PermissionDenied, NotFound

from course_discovery.apps.core.models import Partner
from course_discovery.apps.course_metadata.models import Course, CourseRun, Program

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


class HaystackFacetFilterWithQueries(HaystackFacetFilter):
    query_builder_class = FacetQueryBuilderWithQueries


class HaystackFilter(DefaultHaystackFilter):
    @staticmethod
    def get_request_filters(request):
        filters = HaystackFacetFilter.get_request_filters(request)

        # Return data for the default partner, if no partner is requested
        if not any(field in filters for field in ('partner', 'partner_exact')):
            filters['partner'] = Partner.objects.get(pk=settings.DEFAULT_PARTNER_ID).short_code

        return filters


class CharListFilter(django_filters.CharFilter):
    def filter(self, qs, value):  # pylint: disable=method-hidden
        if value not in (None, ''):
            value = value.split(',')

        return super(CharListFilter, self).filter(qs, value)


class FilterSetMixin:
    def _apply_filter(self, name, queryset, value):
        try:
            if int(value):
                queryset = getattr(queryset, name)()
        except ValueError:
            logger.exception('The "%s" filter requires an integer value of either 0 or 1. %s is invalid', name, value)
            raise

        return queryset

    def filter_active(self, queryset, value):
        return self._apply_filter('active', queryset, value)

    def filter_marketable(self, queryset, value):
        return self._apply_filter('marketable', queryset, value)


class CourseFilter(django_filters.FilterSet):
    keys = CharListFilter(name='key', lookup_type='in')

    class Meta:
        model = Course
        fields = ['keys']


class CourseRunFilter(FilterSetMixin, django_filters.FilterSet):
    active = django_filters.MethodFilter()
    marketable = django_filters.MethodFilter()
    keys = CharListFilter(name='key', lookup_type='in')

    @property
    def qs(self):
        # This endpoint supports query via Haystack. If that form of filtering is active,
        # do not attempt to treat the queryset as a normal Django queryset.
        if not isinstance(self.queryset, QuerySet):
            return self.queryset

        return super(CourseRunFilter, self).qs

    class Meta:
        model = CourseRun
        fields = ['keys']


class ProgramFilter(FilterSetMixin, django_filters.FilterSet):
    marketable = django_filters.MethodFilter()
    type = django_filters.CharFilter(name='type__name', lookup_expr='iexact')
    uuids = CharListFilter(name='uuid', lookup_type='in')

    class Meta:
        model = Program
        fields = ['type', 'uuids']
