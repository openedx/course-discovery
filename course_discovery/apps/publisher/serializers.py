"""Publisher Serializers"""
import waffle
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from rest_framework import serializers

from course_discovery.apps.publisher.emails import send_email_for_studio_instance_created
from course_discovery.apps.publisher.models import CourseRun


class UpdateCourseKeySerializer(serializers.ModelSerializer):
    """Serializer for the `CourseRun` model to update 'lms_course_id'. """

    class Meta:
        model = CourseRun
        fields = ('lms_course_id', 'changed_by',)

    def validate(self, data):
        validated_values = super(UpdateCourseKeySerializer, self).validate(data)
        lms_course_id = validated_values.get('lms_course_id')

        try:
            CourseKey.from_string(lms_course_id)
        except InvalidKeyError:
            raise serializers.ValidationError('Invalid course key [{}]'.format(lms_course_id))

        request = self.context.get('request')
        if request:
            validated_values.update({'changed_by': request.user})

        return validated_values

    def update(self, instance, validated_data):
        instance = super(UpdateCourseKeySerializer, self).update(instance, validated_data)

        if waffle.switch_is_active('enable_publisher_email_notifications'):
            send_email_for_studio_instance_created(instance)

        return instance
