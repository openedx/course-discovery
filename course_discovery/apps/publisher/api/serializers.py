"""Publisher API Serializers"""
import waffle

from django.apps import apps
from django.utils.translation import ugettext_lazy as _
from django_fsm import TransitionNotAllowed
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from rest_framework import serializers

from course_discovery.apps.core.models import User
from course_discovery.apps.publisher.emails import send_email_for_studio_instance_created
from course_discovery.apps.publisher.models import CourseUserRole, CourseRun, CourseState


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


class CourseRevisionSerializer(serializers.ModelSerializer):
    """Serializer for the course history model. """
    primary_subject = serializers.SerializerMethodField()
    secondary_subject = serializers.SerializerMethodField()
    tertiary_subject = serializers.SerializerMethodField()

    class Meta:
        model = apps.get_model('publisher', 'historicalcourse')
        fields = (
            'history_id', 'title', 'number', 'short_description', 'full_description', 'expected_learnings',
            'prerequisites', 'primary_subject', 'secondary_subject', 'tertiary_subject',
        )

    def get_primary_subject(self, obj):
        if obj.primary_subject:
            return obj.primary_subject.name

    def get_secondary_subject(self, obj):
        if obj.secondary_subject:
            return obj.secondary_subject.name

    def get_tertiary_subject(self, obj):
        if obj.tertiary_subject:
            return obj.tertiary_subject.name


class CourseStateSerializer(serializers.ModelSerializer):
    """Serializer for `CourseState` model to change course workflow state. """

    class Meta:
        model = CourseState
        fields = ('name', 'approved_by_role', 'owner_role', 'course',)
        extra_kwargs = {
            'course': {'read_only': True},
            'approved_by_role': {'read_only': True},
            'owner_role': {'read_only': True}
        }

    def update(self, instance, validated_data):
        state = validated_data.get('name')
        try:
            instance.change_state(state=state)
        except TransitionNotAllowed:
            # pylint: disable=no-member
            raise serializers.ValidationError(
                {
                    'name': _('Cannot switch from state `{state}` to `{target_state}`').format(
                        state=instance.name, target_state=state
                    )
                }
            )

        return instance
