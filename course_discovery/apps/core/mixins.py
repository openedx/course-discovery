from dry_rest_permissions.generics import allow_staff_or_superuser, authenticated_users


class ModelPermissionsMixin:
    """ Adds DRY permissions to a model.

    Inheriting models should have the default add, change, and delete permissions, as well as the
    custom "view" permission.
    """

    @classmethod
    def get_permission(cls, action):
        """
        Returns a permission name for the given class and action.

        Arguments:
            action (str): Action tied to the desired permission (e.g. add, change, delete).

        Returns:
            str: Permission
        """
        kwargs = {
            'app_label': cls._meta.app_label,
            'model_name': cls._meta.model_name,
            'action': action
        }
        return '{app_label}.{action}_{model_name}'.format(**kwargs)

    @staticmethod
    @authenticated_users
    def has_read_permission(_request):
        return True

    @staticmethod
    @authenticated_users
    @allow_staff_or_superuser
    def has_write_permission(_request):
        # This is only here to get past the global has_permission check. The object permissions will determine
        # if a specific instance can be updated.
        return True

    @classmethod
    def has_create_permission(cls, request):
        user = request.user
        perm = cls.get_permission('add')
        return user.is_staff or user.is_superuser or user.has_perm(perm)

    @authenticated_users
    @allow_staff_or_superuser
    def has_object_create_permission(self, request):  # pragma: no cover
        # NOTE (CCB): This method is solely here to ensure object creation and permissions behave appropriately
        # when using the Browseable API. This is not called when making a JSON request.
        perm = self.get_permission('add')
        return request.user.has_perm(perm, self)

    @authenticated_users
    @allow_staff_or_superuser
    def has_object_destroy_permission(self, request):
        perm = self.get_permission('delete')
        return request.user.has_perm(perm, self)

    @authenticated_users
    @allow_staff_or_superuser
    def has_object_read_permission(self, request):
        perm = self.get_permission('view')
        return request.user.has_perm(perm, self)

    @authenticated_users
    @allow_staff_or_superuser
    def has_object_update_permission(self, request):
        perm = self.get_permission('change')
        return request.user.has_perm(perm, self)
