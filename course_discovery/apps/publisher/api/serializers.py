"""Publisher API Serializers"""

from rest_framework import serializers

from course_discovery.apps.core.models import User
from course_discovery.apps.publisher.models import CourseUserRole


class CourseUserRoleSerializer(serializers.ModelSerializer):
    """Serializer for the `CourseUserRole` model to change role assignment. """

    class Meta:
        model = CourseUserRole
        fields = ('course', 'user', 'role',)
        read_only_fields = ('course', 'role')

    def validate(self, data):
        validated_values = super(CourseUserRoleSerializer, self).validate(data)

        request = self.context.get('request')
        if request:
            validated_values.update({'changed_by': request.user})

        return validated_values


class GroupUserSerializer(serializers.ModelSerializer):
    """Serializer for the `User` model used in OrganizationGroupUserView. """

    class Meta:
        model = User
        fields = ('id', 'full_name', )
