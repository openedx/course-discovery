"""Publisher API Serializers"""
import re

import waffle
from django.apps import apps
from django.db import transaction
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django_fsm import TransitionNotAllowed
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from rest_framework import serializers

from course_discovery.apps.core.models import User
from course_discovery.apps.course_metadata.models import CourseRun as DiscoveryCourseRun
from course_discovery.apps.publisher.choices import PublisherUserRole
from course_discovery.apps.publisher.emails import (
    send_change_role_assignment_email, send_email_for_studio_instance_created, send_email_preview_accepted,
    send_email_preview_page_is_available
)
from course_discovery.apps.publisher.models import (
    CourseRun, CourseRunState, CourseState, CourseUserRole, OrganizationUserRole
)


class UnvalidatedField(serializers.Field):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.allow_blank = True
        self.allow_null = True

    def to_internal_value(self, data):
        return data

    def to_representation(self, value):
        return value


class CourseUserRoleSerializer(serializers.ModelSerializer):
    """Serializer for the `CourseUserRole` model to change role assignment. """

    class Meta:
        model = CourseUserRole
        fields = ('course', 'user', 'role',)
        read_only_fields = ('course', 'role')

    def validate(self, attrs):
        validated_values = super(CourseUserRoleSerializer, self).validate(attrs)

        request = self.context.get('request')
        if request:
            validated_values.update({'changed_by': request.user})

        return validated_values

    @transaction.atomic
    def update(self, instance, validated_data):
        former_user = instance.user
        instance = super(CourseUserRoleSerializer, self).update(instance, validated_data)
        if not instance.role == PublisherUserRole.CourseTeam:
            request = self.context['request']
            send_change_role_assignment_email(instance, former_user, request.site)

        return instance


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


class CourseRunSerializer(serializers.ModelSerializer):
    """
    Serializer for the `CourseRun` model.
    """
    EXTERNAL_COURSE_KEY_PATTERN = r'[A-Za-z0-9-_:]+'
    preview_url = UnvalidatedField()  # Otherwise the @property method gets stripped from validated_data

    class Meta:
        model = CourseRun
        fields = ('lms_course_id', 'external_key', 'changed_by', 'preview_url',)

    def validate_lms_course_id(self, value):
        try:
            CourseKey.from_string(value)
        except InvalidKeyError:
            raise serializers.ValidationError(
                {'lms_course_id': _('Invalid course key "{lms_course_id}"').format(lms_course_id=value)}
            )

        return value

    def validate_external_key(self, value):
        if value is None:
            return value

        if not re.match(self.EXTERNAL_COURSE_KEY_PATTERN, value):
            raise serializers.ValidationError(
                {'lms_course_id': _('Invalid external course key "{external_key}"').format(external_key=value)}
            )

        return value

    def validate_preview_url(self, value):
        if value is None:
            return value

        if not re.match(r'https?://(?:www)?(?:[\w-]{2,255}(?:\.\w{2,6}){1,2})(?:/[\w&%?#-]{1,300})?', value):
            raise serializers.ValidationError(
                {'preview_url': _('Invalid URL format "{preview_url}"').format(preview_url=value)}
            )

        return value

    def validate(self, attrs):
        validated_values = super(CourseRunSerializer, self).validate(attrs)
        if 'preview_url' in attrs:
            self.validate_preview_url(attrs['preview_url'])

        if validated_values.get('lms_course_id'):
            request = self.context.get('request')
            if request:
                validated_values.update({'changed_by': request.user})

        return validated_values

    def update_preview_url(self, preview_url, course_id):
        # Note: we are assuming the preview URL is mostly right - we don't bother checking hostname etc.
        # This is calculated laziness - publisher has a short shelf life and the URL is presented to the user
        # correctly, so they'd have to go out of their way to muck it up. This approach was preferred over changing
        # the publisher UI to only show a slug, instead of a full URL, simply to save effort.
        slug = preview_url.rstrip('/').rsplit('/', 1)[-1]

        current = DiscoveryCourseRun.objects.filter(key=course_id).first()
        if not current or current.slug == slug:
            return  # nothing to do here

        if DiscoveryCourseRun.objects.filter(slug=slug).exists():
            raise Exception(_('Preview URL already in use for another course'))

        current.slug = slug
        current.save()  # this will push the new slug to the marketing site

    @transaction.atomic
    def update(self, instance, validated_data):
        lms_course_id = validated_data.get('lms_course_id')

        # Handle saving the preview URL as a slug first
        preview_url = validated_data.pop('preview_url', None)
        if preview_url:
            self.update_preview_url(preview_url, lms_course_id or instance.lms_course_id)

        instance = super(CourseRunSerializer, self).update(instance, validated_data)
        request = self.context['request']

        if preview_url:
            # Change ownership to CourseTeam.
            instance.course_run_state.change_owner_role(PublisherUserRole.CourseTeam)

        if waffle.switch_is_active('enable_publisher_email_notifications'):
            if preview_url:
                send_email_preview_page_is_available(instance, site=request.site)

            elif lms_course_id:
                send_email_for_studio_instance_created(instance, site=request.site)

        return instance


class CourseRevisionSerializer(serializers.ModelSerializer):
    """Serializer for the course history model. """
    primary_subject = serializers.SerializerMethodField()
    secondary_subject = serializers.SerializerMethodField()
    tertiary_subject = serializers.SerializerMethodField()
    level_type = serializers.SerializerMethodField()

    class Meta:
        model = apps.get_model('publisher', 'historicalcourse')
        fields = (
            'history_id', 'title', 'number', 'short_description', 'full_description', 'expected_learnings',
            'prerequisites', 'primary_subject', 'secondary_subject', 'tertiary_subject', 'level_type',
            'learner_testimonial', 'faq', 'video_link',
        )

    def get_primary_subject(self, obj):
        if obj.primary_subject:
            return obj.primary_subject.name
        return None

    def get_secondary_subject(self, obj):
        if obj.secondary_subject:
            return obj.secondary_subject.name
        return None

    def get_tertiary_subject(self, obj):
        if obj.tertiary_subject:
            return obj.tertiary_subject.name
        return None

    def get_level_type(self, obj):
        if obj.level_type:
            return obj.level_type.name
        return None


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
        request = self.context.get('request')
        try:
            instance.change_state(state=state, user=request.user, site=request.site)
        except TransitionNotAllowed:
            raise serializers.ValidationError(
                {
                    'name': _('Cannot switch from state `{state}` to `{target_state}`').format(
                        state=instance.name, target_state=state
                    )
                }
            )

        return instance


class CourseRunStateSerializer(serializers.ModelSerializer):
    """
    Serializer for `CourseRunState` model to change course-run workflow state
    or to mark preview as accepted.
    """

    class Meta:
        model = CourseRunState
        fields = ('name', 'approved_by_role', 'owner_role', 'course_run', 'preview_accepted',)
        extra_kwargs = {
            'course_run': {'read_only': True},
            'approved_by_role': {'read_only': True},
            'owner_role': {'read_only': True}
        }

    @transaction.atomic
    def update(self, instance, validated_data):
        request = self.context.get('request')
        state = validated_data.get('name')
        preview_accepted = validated_data.get('preview_accepted')

        if state:
            try:
                instance.change_state(state=state, user=request.user, site=request.site)
            except TransitionNotAllowed:
                raise serializers.ValidationError(
                    {
                        'name': _('Cannot switch from state `{state}` to `{target_state}`').format(
                            state=instance.name, target_state=state
                        )
                    }
                )

        elif preview_accepted:
            # Mark preview accepted and change ownership to Publisher.
            instance.preview_accepted = True
            instance.owner_role = PublisherUserRole.Publisher
            instance.owner_role_modified = timezone.now()
            instance.save()

            if waffle.switch_is_active('enable_publisher_email_notifications'):
                send_email_preview_accepted(instance.course_run, request.site)

        return instance
