from rest_framework.permissions import SAFE_METHODS, BasePermission


class ReadOnlyByPublisherUser(BasePermission):
    """
    Custom Permission class to check user is a publisher user.
    """
    def has_permission(self, request, view):
        if request.method == 'GET':
            return request.user.groups.exists()
        return True


class IsCourseEditorOrReadOnly(BasePermission):
    """
    Custom Permission class to check user is a course editor for the course, if they are trying to write.
    """
    def has_permission(self, request, view):
        if request.method == 'POST':
            # You must be a member of the organization within which you are creating a course
            org = request.data.get('org')
            return org and (
                request.user.is_staff or
                request.user.groups.filter(organization_extension__organization__key=org).exists()
            )
        else:
            return True  # other write access attempts will be caught by object permissions below

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        elif request.user.is_staff:  # staff users are always editors
            return True

        authoring_orgs = obj.authoring_organizations.all()

        # No matter what, if an editor or their organization has been removed from the course, they can't be an editor
        # for it. This handles cases of being dropped from an org... But might be too restrictive in case we want
        # to allow outside guest editors on a course? Let's try this for now and see how it goes.
        valid_editors = obj.editors.filter(user__groups__organization_extension__organization__in=authoring_orgs)

        if not valid_editors.exists():
            # No valid editors - this is an edge case where we just grant anyone in an authoring org access
            return request.user.groups.filter(organization_extension__organization__in=authoring_orgs).exists()
        else:
            return request.user in {x.user for x in valid_editors}
