"""Publisher API Serializers"""
import waffle

from django.utils.translation import ugettext_lazy as _
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from rest_framework import serializers

from course_discovery.apps.core.models import User
from course_discovery.apps.publisher.emails import send_email_for_studio_instance_created
from course_discovery.apps.publisher.models import CourseUserRole, CourseRun


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


class UpdateCourseKeySerializer(serializers.ModelSerializer):
    """
    Serializer for the `CourseRun` model to update 'lms_course_id'.
    """

    class Meta:
        model = CourseRun
        fields = ('lms_course_id', 'changed_by',)

    def validate(self, data):
        validated_values = super(UpdateCourseKeySerializer, self).validate(data)
        lms_course_id = validated_values.get('lms_course_id')

        try:
            CourseKey.from_string(lms_course_id)
        except InvalidKeyError:
            # pylint: disable=no-member
            raise serializers.ValidationError(
                {'lms_course_id': _('Invalid course key "{lms_course_id}"').format(lms_course_id=lms_course_id)}
            )

        request = self.context.get('request')
        if request:
            validated_values.update({'changed_by': request.user})

        return validated_values

    def update(self, instance, validated_data):
        instance = super(UpdateCourseKeySerializer, self).update(instance, validated_data)

        if waffle.switch_is_active('enable_publisher_email_notifications'):
            send_email_for_studio_instance_created(instance)

        return instance
