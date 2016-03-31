from dry_rest_permissions.generics import DRYPermissionFiltersBase
from guardian.shortcuts import get_objects_for_user


class PermissionsFilter(DRYPermissionFiltersBase):
    def filter_list_queryset(self, request, queryset, view):
        """ Filters the list queryset, returning only the objects accessible by the user. """
        perm = queryset.model.get_permission('view')
        return get_objects_for_user(request.user, perm)
