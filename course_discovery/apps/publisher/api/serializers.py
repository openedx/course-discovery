from rest_framework import serializers

from course_discovery.apps.core.models import User
from course_discovery.apps.publisher.models import OrganizationUserRole


class GroupUserSerializer(serializers.ModelSerializer):
    """Serializer for the `User` model used in OrganizationGroupUserView. """
    full_name = serializers.SerializerMethodField('get_user_full_name')

    class Meta:
        model = User
        fields = ('id', 'full_name', 'email')

    def get_user_full_name(self, obj):
        """
        Return full_name if exist otherwise username, to fix empty values in dropdown.
        """
        return obj.get_full_name() or obj.username


class OrganizationUserRoleSerializer(serializers.ModelSerializer):
    """Serializer for the `OrganizationUserRole` model to show role assignment. """
    user = GroupUserSerializer()

    class Meta:
        model = OrganizationUserRole
        fields = ('id', 'user', 'role',)
