import django_filters
from django.contrib.auth import get_user_model
from django.utils.translation import ugettext as _
from drf_haystack.filters import HaystackFacetFilter
from drf_haystack.query import FacetQueryBuilder
from dry_rest_permissions.generics import DRYPermissionFiltersBase
from guardian.shortcuts import get_objects_for_user
from rest_framework.exceptions import PermissionDenied, NotFound

from course_discovery.apps.course_metadata.models import Course

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
    def build_query(self, **filters):
        query = super(FacetQueryBuilderWithQueries, self).build_query(**filters)
        facet_serializer_cls = self.view.get_facet_serializer_class()
        query['query_facets'] = getattr(facet_serializer_cls.Meta, 'field_queries', {})
        return query


class HaystackFacetFilterWithQueries(HaystackFacetFilter):
    query_builder_class = FacetQueryBuilderWithQueries


class CharListFilter(django_filters.CharFilter):
    def filter(self, qs, value):  # pylint: disable=method-hidden
        if value not in (None, ''):
            value = value.split(',')

        return super(CharListFilter, self).filter(qs, value)


class CourseFilter(django_filters.FilterSet):
    keys = CharListFilter(name='key', lookup_type='in')

    class Meta:
        model = Course
        fields = ['keys']
