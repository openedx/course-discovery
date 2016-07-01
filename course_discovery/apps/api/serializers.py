# pylint: disable=abstract-method

from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

from course_discovery.apps.catalogs.models import Catalog
from course_discovery.apps.course_metadata.models import (
    Course, CourseRun, Image, Organization, Person, Prerequisite, Seat, Subject, Video
)
from course_discovery.apps.course_metadata.search_indexes import CourseIndex, CourseRunIndex
from drf_haystack.serializers import HaystackSerializer, HaystackFacetSerializer

User = get_user_model()

COMMON_IGNORED_FIELDS = ('text',)
COMMON_SEARCH_FIELD_ALIASES = {
    'q': 'text',
}
COURSE_RUN_FACET_FIELD_OPTIONS = {
    'level_type': {},
    'organizations': {},
    'prerequisites': {},
    'subjects': {},
    'language': {},
    'transcript_languages': {},
    'pacing_type': {},
    'content_type': {},
    'type': {},
}

COURSE_RUN_FACET_FIELD_QUERIES = {
    'availability_current': {'query': 'start:<now AND end:>now'},
    'availability_starting_soon': {'query': 'start:[now TO now+60d]'},
    'availability_upcoming': {'query': 'start:[now+60d TO *]'},
    'availability_archived': {'query': 'end:<=now'},
}
COURSE_RUN_SEARCH_FIELDS = (
    'key', 'title', 'short_description', 'full_description', 'start', 'end', 'enrollment_start', 'enrollment_end',
    'pacing_type', 'language', 'transcript_languages', 'marketing_url', 'content_type', 'org', 'number', 'seat_types',
    'image_url', 'type', 'text',
)


def get_marketing_url_for_user(user, marketing_url):
    """
    Return the given marketing URL with affiliate query parameters for the user.

    Arguments:
        user (User): the user to use to construct the query parameters.
        marketing_url (str | None): the base URL.

    Returns:
        str | None
    """
    if marketing_url is None:
        return None
    params = urlencode({
        'utm_source': user.username,
        'utm_medium': user.referral_tracking_id,
    })
    return '{url}?{params}'.format(url=marketing_url, params=params)


class TimestampModelSerializer(serializers.ModelSerializer):
    """Serializer for timestamped models."""
    modified = serializers.DateTimeField()


class NamedModelSerializer(serializers.ModelSerializer):
    """Serializer for models inheriting from ``AbstractNamedModel``."""
    name = serializers.CharField()

    class Meta(object):
        fields = ('name',)


class SubjectSerializer(NamedModelSerializer):
    """Serializer for the ``Subject`` model."""

    class Meta(NamedModelSerializer.Meta):
        model = Subject


class PrerequisiteSerializer(NamedModelSerializer):
    """Serializer for the ``Prerequisite`` model."""

    class Meta(NamedModelSerializer.Meta):
        model = Prerequisite


class MediaSerializer(serializers.ModelSerializer):
    """Serializer for models inheriting from ``AbstractMediaModel``."""
    src = serializers.CharField()
    description = serializers.CharField()


class ImageSerializer(MediaSerializer):
    """Serializer for the ``Image`` model."""
    height = serializers.IntegerField()
    width = serializers.IntegerField()

    class Meta(object):
        model = Image
        fields = ('src', 'description', 'height', 'width')


class VideoSerializer(MediaSerializer):
    """Serializer for the ``Video`` model."""
    image = ImageSerializer()

    class Meta(object):
        model = Video
        fields = ('src', 'description', 'image',)


class SeatSerializer(serializers.ModelSerializer):
    """Serializer for the ``Seat`` model."""
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
    """Serializer for the ``Person`` model."""
    profile_image = ImageSerializer()

    class Meta(object):
        model = Person
        fields = ('key', 'name', 'title', 'bio', 'profile_image',)


class OrganizationSerializer(serializers.ModelSerializer):
    """Serializer for the ``Organization`` model."""
    logo_image = ImageSerializer()

    class Meta(object):
        model = Organization
        fields = ('key', 'name', 'description', 'logo_image', 'homepage_url',)


class CatalogSerializer(serializers.ModelSerializer):
    """Serializer for the ``Catalog`` model."""
    courses_count = serializers.IntegerField(read_only=True, help_text=_('Number of courses contained in this catalog'))
    viewers = serializers.SlugRelatedField(slug_field='username', queryset=User.objects.all(), many=True,
                                           allow_null=True, allow_empty=True, required=False,
                                           help_text=_('Usernames of users with explicit access to view this catalog'))

    def create(self, validated_data):
        viewers = validated_data.pop('viewers')
        viewers = User.objects.filter(username__in=viewers)

        # Set viewers after the model has been saved
        instance = super(CatalogSerializer, self).create(validated_data)
        instance.viewers = viewers
        instance.save()
        return instance

    class Meta(object):
        model = Catalog
        fields = ('id', 'name', 'query', 'courses_count', 'viewers')


class CourseRunSerializer(TimestampModelSerializer):
    """Serializer for the ``CourseRun`` model."""
    course = serializers.SlugRelatedField(read_only=True, slug_field='key')
    content_language = serializers.SlugRelatedField(
        read_only=True, slug_field='code', source='language',
        help_text=_('Language in which the course is administered')
    )
    transcript_languages = serializers.SlugRelatedField(many=True, read_only=True, slug_field='code')
    image = ImageSerializer()
    video = VideoSerializer()
    seats = SeatSerializer(many=True)
    instructors = PersonSerializer(many=True)
    staff = PersonSerializer(many=True)
    marketing_url = serializers.SerializerMethodField()

    class Meta(object):
        model = CourseRun
        fields = (
            'course', 'key', 'title', 'short_description', 'full_description', 'start', 'end',
            'enrollment_start', 'enrollment_end', 'announcement', 'image', 'video', 'seats',
            'content_language', 'transcript_languages', 'instructors', 'staff',
            'pacing_type', 'min_effort', 'max_effort', 'modified', 'marketing_url',
        )

    def get_marketing_url(self, obj):
        return get_marketing_url_for_user(self.context['request'].user, obj.marketing_url)


class ContainedCourseRunsSerializer(serializers.Serializer):
    """Serializer used to represent course runs contained by a catalog."""
    course_runs = serializers.DictField(
        child=serializers.BooleanField(),
        help_text=_('Dictionary mapping course run IDs to boolean values')
    )


class CourseSerializer(TimestampModelSerializer):
    """Serializer for the ``Course`` model."""
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
        return get_marketing_url_for_user(self.context['request'].user, obj.marketing_url)


class CourseSerializerExcludingClosedRuns(CourseSerializer):
    """A ``CourseSerializer`` which only includes active course runs, as determined by ``CourseQuerySet``."""
    course_runs = CourseRunSerializer(many=True, source='active_course_runs')


class ContainedCoursesSerializer(serializers.Serializer):
    """Serializer used to represent courses contained by a catalog."""
    courses = serializers.DictField(
        child=serializers.BooleanField(),
        help_text=_('Dictionary mapping course IDs to boolean values')
    )


class AffiliateWindowSerializer(serializers.ModelSerializer):
    """ Serializer for Affiliate Window product feeds. """

    # We use a hardcoded value since it is determined by Affiliate Window's taxonomy.
    CATEGORY = 'Other Experiences'

    pid = serializers.SerializerMethodField()
    name = serializers.CharField(source='course_run.title')
    desc = serializers.CharField(source='course_run.short_description')
    purl = serializers.CharField(source='course_run.marketing_url')
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
        return self.CATEGORY


class FlattenedCourseRunWithCourseSerializer(CourseRunSerializer):
    seats = serializers.SerializerMethodField()
    owners = serializers.SerializerMethodField()
    sponsors = serializers.SerializerMethodField()
    subjects = serializers.SerializerMethodField()
    prerequisites = serializers.SerializerMethodField()
    level_type = serializers.SerializerMethodField()
    expected_learning_items = serializers.SerializerMethodField()
    course_key = serializers.SerializerMethodField()

    class Meta(object):
        model = CourseRun
        fields = (
            'key', 'title', 'short_description', 'full_description', 'level_type', 'subjects', 'prerequisites',
            'start', 'end', 'enrollment_start', 'enrollment_end', 'announcement', 'seats', 'content_language',
            'transcript_languages', 'instructors', 'staff', 'pacing_type', 'min_effort', 'max_effort', 'course_key',
            'expected_learning_items', 'image', 'video', 'owners', 'sponsors', 'modified', 'marketing_url',
        )

    def get_seats(self, obj):
        seats = {
            'audit': {
                'type': ''
            },
            'honor': {
                'type': ''
            },
            'verified': {
                'type': '',
                'currency': '',
                'price': '',
                'upgrade_deadline': '',
            },
            'professional': {
                'type': '',
                'currency': '',
                'price': '',
                'upgrade_deadline': '',
            },
            'credit': {
                'type': [],
                'currency': [],
                'price': [],
                'upgrade_deadline': [],
                'credit_provider': [],
                'credit_hours': [],
            },
        }

        for seat in obj.seats.all():
            for key in seats[seat.type].keys():
                if seat.type == 'credit':
                    seats['credit'][key].append(SeatSerializer(seat).data[key])
                else:
                    seats[seat.type][key] = SeatSerializer(seat).data[key]

        for credit_attr in seats['credit'].keys():
            seats['credit'][credit_attr] = ','.join([str(e) for e in seats['credit'][credit_attr]])

        return seats

    def get_owners(self, obj):
        return ','.join([owner.key for owner in obj.course.owners.all()])

    def get_sponsors(self, obj):
        return ','.join([sponsor.key for sponsor in obj.course.sponsors.all()])

    def get_subjects(self, obj):
        return ','.join([subject.name for subject in obj.course.subjects.all()])

    def get_prerequisites(self, obj):
        return ','.join([prerequisite.name for prerequisite in obj.course.prerequisites.all()])

    def get_expected_learning_items(self, obj):
        return ','.join(
            [expected_learning_item.value for expected_learning_item in obj.course.expected_learning_items.all()]
        )

    def get_level_type(self, obj):
        return obj.course.level_type

    def get_course_key(self, obj):
        return obj.course.key


class CourseSearchSerializer(HaystackSerializer):
    content_type = serializers.CharField(source='model_name')

    class Meta:
        field_aliases = COMMON_SEARCH_FIELD_ALIASES
        fields = ('key', 'title', 'short_description', 'full_description', 'text',)
        ignore_fields = COMMON_IGNORED_FIELDS
        index_classes = [CourseIndex]


class CourseFacetSerializer(HaystackFacetSerializer):
    serialize_objects = True

    class Meta:
        field_aliases = COMMON_SEARCH_FIELD_ALIASES
        field_options = {
            'level_type': {},
            'organizations': {},
            'prerequisites': {},
            'subjects': {},
        }
        ignore_fields = COMMON_IGNORED_FIELDS


class CourseRunSearchSerializer(HaystackSerializer):
    content_type = serializers.CharField(source='model_name')

    class Meta:
        field_aliases = COMMON_SEARCH_FIELD_ALIASES
        fields = COURSE_RUN_SEARCH_FIELDS
        ignore_fields = COMMON_IGNORED_FIELDS
        index_classes = [CourseRunIndex]


class CourseRunFacetSerializer(HaystackFacetSerializer):
    serialize_objects = True

    class Meta:
        field_aliases = COMMON_SEARCH_FIELD_ALIASES
        field_options = COURSE_RUN_FACET_FIELD_OPTIONS
        field_queries = COURSE_RUN_FACET_FIELD_QUERIES
        ignore_fields = COMMON_IGNORED_FIELDS


class AggregateSearchSerializer(HaystackSerializer):
    class Meta:
        field_aliases = COMMON_SEARCH_FIELD_ALIASES
        fields = COURSE_RUN_SEARCH_FIELDS
        ignore_fields = COMMON_IGNORED_FIELDS
        serializers = {
            CourseRunIndex: CourseRunSearchSerializer,
            CourseIndex: CourseSearchSerializer,
        }


class AggregateFacetSearchSerializer(HaystackFacetSerializer):
    serialize_objects = True

    class Meta:
        field_aliases = COMMON_SEARCH_FIELD_ALIASES
        field_options = COURSE_RUN_FACET_FIELD_OPTIONS
        field_queries = COURSE_RUN_FACET_FIELD_QUERIES
        ignore_fields = COMMON_IGNORED_FIELDS
        serializers = {
            CourseRunIndex: CourseRunFacetSerializer,
            CourseIndex: CourseFacetSerializer,
        }
