from django_filters import rest_framework as filters

from course_discovery.apps.api.filters import CharListFilter
from course_discovery.apps.publisher.models import OrganizationUserRole


class OrganizationUserRoleFilterSet(filters.FilterSet):
    role = CharListFilter(field_name='role', lookup_expr='in')

    class Meta:
        model = OrganizationUserRole
        fields = ('role',)
