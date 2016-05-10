from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

from course_discovery.apps.catalogs.models import Catalog
from course_discovery.apps.course_metadata.models import (
    Course, CourseRun, Image, Organization, Person, Prerequisite, Seat, Subject, Video
)

User = get_user_model()


class TimestampModelSerializer(serializers.ModelSerializer):
    modified = serializers.DateTimeField()


class NamedModelSerializer(serializers.ModelSerializer):
    name = serializers.CharField()

    class Meta(object):
        fields = ('name',)


class SubjectSerializer(NamedModelSerializer):
    class Meta(NamedModelSerializer.Meta):
        model = Subject


class PrerequisiteSerializer(NamedModelSerializer):
    class Meta(NamedModelSerializer.Meta):
        model = Prerequisite


class MediaSerializer(serializers.ModelSerializer):
    src = serializers.CharField()
    description = serializers.CharField()


class ImageSerializer(MediaSerializer):
    height = serializers.IntegerField()
    width = serializers.IntegerField()

    class Meta(object):
        model = Image
        fields = ('src', 'description', 'height', 'width')


class VideoSerializer(MediaSerializer):
    image = ImageSerializer()

    class Meta(object):
        model = Video
        fields = ('src', 'description', 'image',)


class SeatSerializer(serializers.ModelSerializer):
    type = serializers.ChoiceField(
        choices=[name for name, __ in Seat.SEAT_TYPE_CHOICES]
    )
    price = serializers.DecimalField(
        decimal_places=Seat.PRICE_FIELD_CONFIG['decimal_places'],
        max_digits=Seat.PRICE_FIELD_CONFIG['max_digits']
    )
    currency = serializers.SlugRelatedField(read_only=True, slug_field='code')
    upgrade_deadline = serializers.DateTimeField()
    credit_provider = serializers.CharField()
    credit_hours = serializers.IntegerField()

    class Meta(object):
        model = Seat
        fields = ('type', 'price', 'currency', 'upgrade_deadline', 'credit_provider', 'credit_hours',)


class PersonSerializer(serializers.ModelSerializer):
    profile_image = ImageSerializer()

    class Meta(object):
        model = Person
        fields = ('key', 'name', 'title', 'bio', 'profile_image',)


class OrganizationSerializer(serializers.ModelSerializer):
    logo_image = ImageSerializer()

    class Meta(object):
        model = Organization
        fields = ('key', 'name', 'description', 'logo_image', 'homepage_url',)


class CatalogSerializer(serializers.ModelSerializer):
    courses_count = serializers.IntegerField(read_only=True, help_text=_('Number of courses contained in this catalog'))
    viewers = serializers.SlugRelatedField(slug_field='username', queryset=User.objects.all(), many=True,
                                           allow_null=True, allow_empty=True, required=False,
                                           help_text=_('Usernames of users with explicit access to view this catalog'))

    def is_valid(self, **kwargs):
        # Ensure that the catalog's viewers actually exist in the
        # DB. We keep this in a transaction so that users are only
        # created if the data is valid.
        sid = transaction.savepoint()
        for username in self.initial_data.get('viewers', ()):  # pylint: disable=no-member
            User.objects.get_or_create(username=username)
        if super().is_valid(**kwargs):
            # Data is good; commit the transaction.
            transaction.savepoint_commit(sid)
            return True
        else:
            # Invalid data; roll back the user creation.
            transaction.savepoint_rollback(sid)
            return False

    def create(self, validated_data):
        viewers = set()
        for username in validated_data.pop('viewers'):
            user = User.objects.get(username=username)
            viewers.add(user)
        # Set viewers after the model has been saved
        instance = super(CatalogSerializer, self).create(validated_data)
        instance.viewers = viewers
        instance.save()
        return instance

    class Meta(object):
        model = Catalog
        fields = ('id', 'name', 'query', 'courses_count', 'viewers')


class CourseRunSerializer(TimestampModelSerializer):
    course = serializers.SlugRelatedField(read_only=True, slug_field='key')
    content_language = serializers.SlugRelatedField(read_only=True, slug_field='code', source='language')
    transcript_languages = serializers.SlugRelatedField(many=True, read_only=True, slug_field='code')
    image = ImageSerializer()
    video = VideoSerializer()
    seats = SeatSerializer(many=True)
    instructors = PersonSerializer(many=True)
    staff = PersonSerializer(many=True)

    class Meta(object):
        model = CourseRun
        fields = (
            'course', 'key', 'title', 'short_description', 'full_description', 'start', 'end',
            'enrollment_start', 'enrollment_end', 'announcement', 'image', 'video', 'seats',
            'content_language', 'transcript_languages', 'instructors', 'staff',
            'pacing_type', 'min_effort', 'max_effort', 'modified',
        )


class CourseSerializer(TimestampModelSerializer):
    level_type = serializers.SlugRelatedField(read_only=True, slug_field='name')
    subjects = SubjectSerializer(many=True)
    prerequisites = PrerequisiteSerializer(many=True)
    expected_learning_items = serializers.SlugRelatedField(many=True, read_only=True, slug_field='value')
    image = ImageSerializer()
    video = VideoSerializer()
    owners = OrganizationSerializer(many=True)
    sponsors = OrganizationSerializer(many=True)
    course_runs = CourseRunSerializer(many=True)
    marketing_url = serializers.SerializerMethodField()

    class Meta(object):
        model = Course
        fields = (
            'key', 'title', 'short_description', 'full_description', 'level_type', 'subjects', 'prerequisites',
            'expected_learning_items', 'image', 'video', 'owners', 'sponsors', 'modified', 'course_runs',
            'marketing_url'
        )

    def get_marketing_url(self, obj):
        if obj.marketing_url is None:
            return None
        user = self.context['request'].user
        params = urlencode({
            'utm_source': user.username,
            'utm_medium': user.referral_tracking_id,
        })
        return '{url}?{params}'.format(url=obj.marketing_url, params=params)


class CourseSerializerExcludingClosedRuns(CourseSerializer):
    course_runs = CourseRunSerializer(many=True, source='active_course_runs')


class ContainedCoursesSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    courses = serializers.DictField(
        child=serializers.BooleanField(),
        help_text=_('Dictionary mapping course IDs to boolean values')
    )


class AffiliateWindowSerializer(serializers.ModelSerializer):
    pid = serializers.SerializerMethodField()
    name = serializers.CharField(source='course_run.course.title')
    desc = serializers.CharField(source='course_run.course.short_description')
    purl = serializers.CharField(source='course_run.course.marketing_url')
    imgurl = serializers.CharField(source='course_run.image')
    category = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()

    class Meta(object):
        model = Seat
        fields = (
            'name', 'pid', 'desc', 'category', 'purl', 'imgurl', 'price', 'currency'
        )

    def get_pid(self, obj):
        return '{}-{}'.format(obj.course_run.key, obj.type)

    def get_price(self, obj):
        return {
            'actualp': obj.price
        }

    def get_category(self, obj):  # pylint: disable=unused-argument
        # Using hardcoded value for category. This value comes from an Affiliate Window taxonomy.
        return 'Other Experiences'
