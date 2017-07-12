# pylint: disable=abstract-method,no-member
import datetime
import json
from urllib.parse import urlencode

import pytz
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models.query import Prefetch
from django.utils.translation import ugettext_lazy as _
from drf_haystack.serializers import HaystackFacetSerializer, HaystackSerializer
from rest_framework import serializers
from rest_framework.fields import DictField
from taggit_serializer.serializers import TaggitSerializer, TagListSerializerField

from course_discovery.apps.api.fields import ImageField, StdImageSerializerField
from course_discovery.apps.catalogs.models import Catalog
from course_discovery.apps.course_metadata.choices import CourseRunStatus, ProgramStatus
from course_discovery.apps.course_metadata.models import (FAQ, CorporateEndorsement, Course, CourseRun, Endorsement,
                                                          Image, Organization, Person, PersonSocialNetwork, PersonWork,
                                                          Position, Prerequisite, Program, ProgramType, Seat, Subject,
                                                          Video)
from course_discovery.apps.course_metadata.search_indexes import CourseIndex, CourseRunIndex, ProgramIndex

User = get_user_model()

COMMON_IGNORED_FIELDS = ('text',)
COMMON_SEARCH_FIELD_ALIASES = {
    'q': 'text',
}
COURSE_RUN_FACET_FIELD_OPTIONS = {
    'level_type': {},
    'organizations': {'size': settings.SEARCH_FACET_LIMIT},
    'prerequisites': {},
    'subjects': {},
    'language': {},
    'transcript_languages': {},
    'pacing_type': {},
    'content_type': {},
    'type': {},
    'seat_types': {},
    'mobile_available': {},
}

COURSE_RUN_FACET_FIELD_QUERIES = {
    'availability_current': {'query': 'start:<now AND end:>now'},
    'availability_starting_soon': {'query': 'start:[now TO now+60d]'},
    'availability_upcoming': {'query': 'start:[now+60d TO *]'},
    'availability_archived': {'query': 'end:<=now'},
}
COURSE_RUN_SEARCH_FIELDS = (
    'text', 'key', 'title', 'short_description', 'full_description', 'start', 'end', 'enrollment_start',
    'enrollment_end', 'pacing_type', 'language', 'transcript_languages', 'marketing_url', 'content_type', 'org',
    'number', 'seat_types', 'image_url', 'type', 'level_type', 'availability', 'published', 'partner', 'program_types',
    'authoring_organization_uuids', 'subject_uuids', 'staff_uuids', 'mobile_available', 'logo_image_urls',
    'aggregation_key', 'min_effort', 'max_effort', 'weeks_to_complete',
)

PROGRAM_FACET_FIELD_OPTIONS = {
    'status': {},
    'type': {},
    'seat_types': {},
}

BASE_PROGRAM_FIELDS = (
    'text', 'uuid', 'title', 'subtitle', 'type', 'marketing_url', 'content_type', 'status', 'card_image_url',
    'published', 'partner', 'language',
)

PROGRAM_SEARCH_FIELDS = BASE_PROGRAM_FIELDS + (
    'aggregation_key', 'authoring_organizations', 'authoring_organization_uuids', 'subject_uuids', 'staff_uuids',
    'weeks_to_complete_min', 'weeks_to_complete_max', 'min_hours_effort_per_week', 'max_hours_effort_per_week',
    'hidden',
)

PROGRAM_FACET_FIELDS = BASE_PROGRAM_FIELDS + ('organizations',)

PREFETCH_FIELDS = {
    'course_run': [
        'course__level_type',
        'course__partner',
        'course__programs',
        'course__programs__partner',
        'course__programs__type',
        'course__programs__excluded_course_runs',
        'language',
        'seats',
        'seats__currency',
        'staff',
        'staff__position',
        'staff__position__organization',
        'transcript_languages',
    ],
    'course': [
        'authoring_organizations',
        'authoring_organizations__partner',
        'authoring_organizations__tags',
        'course_runs',
        'expected_learning_items',
        'level_type',
        'prerequisites',
        'programs',
        'sponsoring_organizations',
        'sponsoring_organizations__partner',
        'sponsoring_organizations__tags',
        'subjects',
        'video',
    ],
}

SELECT_RELATED_FIELDS = {
    'course': ['level_type', 'partner', 'video'],
    'course_run': ['course', 'language', 'video'],
}


def get_marketing_url_for_user(user, marketing_url, exclude_utm=False):
    """
    Return the given marketing URL with affiliate query parameters for the user.

    Arguments:
        user (User): Used to construct UTM query parameters.
        marketing_url (str | None): Base URL to which UTM parameters may be appended.

    Keyword Arguments:
        exclude_utm (bool): Whether to exclude UTM parameters from marketing URLs.

    Returns:
        str | None
    """
    if not marketing_url:
        return None
    elif exclude_utm:
        return marketing_url
    else:
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


class FAQSerializer(serializers.ModelSerializer):
    """Serializer for the ``FAQ`` model."""

    class Meta(object):
        model = FAQ
        fields = ('question', 'answer',)


class SubjectSerializer(serializers.ModelSerializer):
    """Serializer for the ``Subject`` model."""

    class Meta(object):
        model = Subject
        fields = ('name', 'subtitle', 'description', 'banner_image_url', 'card_image_url', 'slug',)


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


class PositionSerializer(serializers.ModelSerializer):
    """Serializer for the ``Position`` model."""

    class Meta(object):
        model = Position
        fields = ('title', 'organization_name', 'organization')
        extra_kwargs = {
            'organization': {'write_only': True}
        }


class PersonSerializer(serializers.ModelSerializer):
    """Serializer for the ``Person`` model."""
    position = PositionSerializer(required=False)
    profile_image = StdImageSerializerField(required=False)
    works = serializers.SlugRelatedField(many=True, read_only=True, slug_field='value', source='person_works')
    urls = serializers.SerializerMethodField()
    email = serializers.EmailField(required=True)

    @classmethod
    def prefetch_queryset(cls):
        return Person.objects.all().select_related(
            'position__organization'
        ).prefetch_related('person_works', 'person_networks')

    class Meta(object):
        model = Person
        fields = (
            'uuid', 'given_name', 'family_name', 'bio', 'profile_image_url', 'slug', 'position', 'profile_image',
            'partner', 'works', 'urls', 'email'
        )
        extra_kwargs = {
            'partner': {'write_only': True}
        }

    def validate(self, data):
        validated_data = super(PersonSerializer, self).validate(data)
        validated_data['works'] = self.initial_data.get('works', [])
        validated_data['urls'] = self.initial_data.get('urls')
        return validated_data

    def create(self, validated_data):
        position_data = validated_data.pop('position')
        works_data = validated_data.pop('works', [])
        urls_data = validated_data.pop('urls', {})

        person = Person.objects.create(**validated_data)
        Position.objects.create(person=person, **position_data)

        person_social_networks = []
        for url_type in [PersonSocialNetwork.FACEBOOK, PersonSocialNetwork.TWITTER, PersonSocialNetwork.BLOG]:
            value = urls_data.get(url_type)
            if value:
                person_social_networks.append(PersonSocialNetwork(person=person, type=url_type, value=value))
        PersonSocialNetwork.objects.bulk_create(person_social_networks)

        person_works = [PersonWork(person=person, value=work_data) for work_data in works_data]
        PersonWork.objects.bulk_create(person_works)

        return person

    def update(self, instance, validated_data):
        position_data = validated_data.pop('position')
        works_data = validated_data.pop('works', [])
        urls_data = validated_data.pop('urls', {})

        instance.position.title = position_data['title']
        instance.position.organization = position_data['organization']
        instance.position.save()

        for url_type in [PersonSocialNetwork.FACEBOOK, PersonSocialNetwork.TWITTER, PersonSocialNetwork.BLOG]:
            value = urls_data.get(url_type)
            if value:
                network, __ = PersonSocialNetwork.objects.get_or_create(person=instance, type=url_type)
                network.value = value
                network.save()
            else:
                PersonSocialNetwork.objects.filter(person=instance, type=url_type).delete()

        instance.person_works.exclude(value__in=works_data).delete()
        for work in works_data:
            PersonWork.objects.get_or_create(person=instance, value=work)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        return instance

    def get_social_network_url(self, url_type, obj):
        # filter() isn't used to avoid discarding prefetched results.
        social_networks = [network for network in obj.person_networks.all() if network.type == url_type]

        if social_networks:
            return social_networks[0].value

    def get_urls(self, obj):
        return {
            PersonSocialNetwork.FACEBOOK: self.get_social_network_url(PersonSocialNetwork.FACEBOOK, obj),
            PersonSocialNetwork.TWITTER: self.get_social_network_url(PersonSocialNetwork.TWITTER, obj),
            PersonSocialNetwork.BLOG: self.get_social_network_url(PersonSocialNetwork.BLOG, obj),
        }


class EndorsementSerializer(serializers.ModelSerializer):
    """Serializer for the ``Endorsement`` model."""
    endorser = PersonSerializer()

    @classmethod
    def prefetch_queryset(cls):
        return Endorsement.objects.all().select_related('endorser')

    class Meta(object):
        model = Endorsement
        fields = ('endorser', 'quote',)


class CorporateEndorsementSerializer(serializers.ModelSerializer):
    """Serializer for the ``CorporateEndorsement`` model."""
    image = ImageSerializer()
    individual_endorsements = EndorsementSerializer(many=True)

    @classmethod
    def prefetch_queryset(cls):
        return CorporateEndorsement.objects.all().select_related('image').prefetch_related(
            Prefetch('individual_endorsements', queryset=EndorsementSerializer.prefetch_queryset()),
        )

    class Meta(object):
        model = CorporateEndorsement
        fields = ('corporation_name', 'statement', 'image', 'individual_endorsements',)


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
    sku = serializers.CharField()

    @classmethod
    def prefetch_queryset(cls):
        return Seat.objects.all().select_related('currency')

    class Meta(object):
        model = Seat
        fields = ('type', 'price', 'currency', 'upgrade_deadline', 'credit_provider', 'credit_hours', 'sku',)


class MinimalOrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ('uuid', 'key', 'name',)


class OrganizationSerializer(TaggitSerializer, MinimalOrganizationSerializer):
    """Serializer for the ``Organization`` model."""
    tags = TagListSerializerField()

    @classmethod
    def prefetch_queryset(cls):
        return Organization.objects.all().select_related('partner').prefetch_related('tags')

    class Meta(MinimalOrganizationSerializer.Meta):
        fields = MinimalOrganizationSerializer.Meta.fields + (
            'certificate_logo_image_url', 'description', 'homepage_url', 'tags', 'logo_image_url', 'marketing_url',
        )


class CatalogSerializer(serializers.ModelSerializer):
    """Serializer for the ``Catalog`` model."""
    courses_count = serializers.IntegerField(read_only=True, help_text=_('Number of courses contained in this catalog'))
    viewers = serializers.SlugRelatedField(slug_field='username', queryset=User.objects.all(), many=True,
                                           allow_null=True, allow_empty=True, required=False,
                                           help_text=_('Usernames of users with explicit access to view this catalog'),
                                           style={'base_template': 'input.html'})

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


class NestedProgramSerializer(serializers.ModelSerializer):
    """
    Serializer used when nesting a Program inside another entity (e.g. a Course). The resulting data includes only
    the basic details of the Program and none of the details about its related entities (e.g. courses).
    """
    type = serializers.SlugRelatedField(slug_field='name', queryset=ProgramType.objects.all())

    class Meta:
        model = Program
        fields = ('uuid', 'title', 'type', 'marketing_slug', 'marketing_url',)
        read_only_fields = ('uuid', 'marketing_url',)


class MinimalCourseRunSerializer(TimestampModelSerializer):
    image = ImageField(read_only=True, source='card_image_url')
    marketing_url = serializers.SerializerMethodField()
    seats = SeatSerializer(many=True)

    @classmethod
    def prefetch_queryset(cls, queryset=None):
        # Explicitly check for None to avoid returning all CourseRuns when the
        # queryset passed in happens to be empty.
        queryset = queryset if queryset is not None else CourseRun.objects.all()

        return queryset.select_related('course').prefetch_related(
            'course__partner',
            Prefetch('seats', queryset=SeatSerializer.prefetch_queryset()),
        )

    class Meta:
        model = CourseRun
        fields = ('key', 'uuid', 'title', 'image', 'short_description', 'marketing_url', 'seats',
                  'start', 'end', 'enrollment_start', 'enrollment_end', 'pacing_type', 'type', 'status',)

    def get_marketing_url(self, obj):
        return get_marketing_url_for_user(
            self.context['request'].user,
            obj.marketing_url,
            exclude_utm=self.context.get('exclude_utm')
        )


class CourseRunSerializer(MinimalCourseRunSerializer):
    """Serializer for the ``CourseRun`` model."""
    course = serializers.SlugRelatedField(read_only=True, slug_field='key')
    content_language = serializers.SlugRelatedField(
        read_only=True, slug_field='code', source='language',
        help_text=_('Language in which the course is administered')
    )
    transcript_languages = serializers.SlugRelatedField(many=True, read_only=True, slug_field='code')
    video = VideoSerializer()
    seats = SeatSerializer(many=True)
    instructors = serializers.SerializerMethodField(help_text='This field is deprecated. Use staff.')
    staff = PersonSerializer(many=True)
    level_type = serializers.SlugRelatedField(read_only=True, slug_field='name')

    @classmethod
    def prefetch_queryset(cls, queryset=None):
        queryset = super().prefetch_queryset(queryset=queryset)

        return queryset.select_related('language', 'video').prefetch_related(
            'course__level_type',
            'transcript_languages',
            'video__image',
            Prefetch('staff', queryset=PersonSerializer.prefetch_queryset()),
        )

    class Meta(MinimalCourseRunSerializer.Meta):
        fields = MinimalCourseRunSerializer.Meta.fields + (
            'course', 'full_description', 'announcement', 'video', 'seats', 'content_language',
            'transcript_languages', 'instructors', 'staff', 'min_effort', 'max_effort', 'modified',
            'level_type', 'availability', 'mobile_available', 'hidden', 'reporting_type', 'eligible_for_financial_aid'
        )

    def get_instructors(self, obj):  # pylint: disable=unused-argument
        # This field is deprecated. Use the staff field.
        return []


class CourseRunWithProgramsSerializer(CourseRunSerializer):
    """A ``CourseRunSerializer`` which includes programs derived from parent course."""
    programs = serializers.SerializerMethodField()

    @classmethod
    def prefetch_queryset(cls, queryset=None):
        queryset = super().prefetch_queryset(queryset=queryset)

        return queryset.prefetch_related('course__programs__excluded_course_runs')

    def get_programs(self, obj):
        programs = []
        # Filter out non-deleted programs which this course_run is part of the program course_run exclusion
        if obj.programs:
            programs = [program for program in obj.programs.all()
                        if (self.context.get('include_deleted_programs') or
                            program.status != ProgramStatus.Deleted) and
                        obj.id not in (run.id for run in program.excluded_course_runs.all())]
            # If flag is not set, remove programs from list that are unpublished
            if not self.context.get('include_unpublished_programs'):
                programs = [program for program in programs if program.status != ProgramStatus.Unpublished]

        return NestedProgramSerializer(programs, many=True).data

    class Meta(CourseRunSerializer.Meta):
        model = CourseRun
        fields = CourseRunSerializer.Meta.fields + ('programs',)


class ContainedCourseRunsSerializer(serializers.Serializer):
    """Serializer used to represent course runs contained by a catalog."""
    course_runs = serializers.DictField(
        child=serializers.BooleanField(),
        help_text=_('Dictionary mapping course run IDs to boolean values')
    )


class MinimalCourseSerializer(TimestampModelSerializer):
    course_runs = MinimalCourseRunSerializer(many=True)
    owners = MinimalOrganizationSerializer(many=True, source='authoring_organizations')
    image = ImageField(read_only=True, source='card_image_url')

    @classmethod
    def prefetch_queryset(cls, queryset=None, course_runs=None):
        # Explicitly check for None to avoid returning all Courses when the
        # queryset passed in happens to be empty.
        queryset = queryset if queryset is not None else Course.objects.all()

        return queryset.select_related('partner').prefetch_related(
            'authoring_organizations',
            Prefetch('course_runs', queryset=MinimalCourseRunSerializer.prefetch_queryset(queryset=course_runs)),
        )

    class Meta:
        model = Course
        fields = ('key', 'uuid', 'title', 'course_runs', 'owners', 'image',)


class CourseSerializer(MinimalCourseSerializer):
    """Serializer for the ``Course`` model."""
    level_type = serializers.SlugRelatedField(read_only=True, slug_field='name')
    subjects = SubjectSerializer(many=True)
    prerequisites = PrerequisiteSerializer(many=True)
    expected_learning_items = serializers.SlugRelatedField(many=True, read_only=True, slug_field='value')
    video = VideoSerializer()
    owners = OrganizationSerializer(many=True, source='authoring_organizations')
    sponsors = OrganizationSerializer(many=True, source='sponsoring_organizations')
    course_runs = CourseRunSerializer(many=True)
    marketing_url = serializers.SerializerMethodField()

    @classmethod
    def prefetch_queryset(cls, queryset=None, course_runs=None):
        # Explicitly check for None to avoid returning all Courses when the
        # queryset passed in happens to be empty.
        queryset = queryset if queryset is not None else Course.objects.all()

        return queryset.select_related('level_type', 'video', 'partner').prefetch_related(
            'expected_learning_items',
            'prerequisites',
            'subjects',
            Prefetch('course_runs', queryset=CourseRunSerializer.prefetch_queryset(queryset=course_runs)),
            Prefetch('authoring_organizations', queryset=OrganizationSerializer.prefetch_queryset()),
            Prefetch('sponsoring_organizations', queryset=OrganizationSerializer.prefetch_queryset()),
        )

    class Meta(MinimalCourseSerializer.Meta):
        model = Course
        fields = MinimalCourseSerializer.Meta.fields + (
            'short_description', 'full_description', 'level_type', 'subjects', 'prerequisites',
            'expected_learning_items', 'video', 'sponsors', 'modified', 'marketing_url',
        )

    def get_marketing_url(self, obj):
        return get_marketing_url_for_user(
            self.context['request'].user,
            obj.marketing_url,
            exclude_utm=self.context.get('exclude_utm')
        )


class CourseWithProgramsSerializer(CourseSerializer):
    """A ``CourseSerializer`` which includes programs."""
    course_runs = serializers.SerializerMethodField()
    programs = serializers.SerializerMethodField()

    @classmethod
    def prefetch_queryset(cls, queryset=None, course_runs=None):
        """
        Similar to the CourseSerializer's prefetch_queryset, but prefetches a
        filtered CourseRun queryset.
        """
        queryset = queryset if queryset is not None else Course.objects.all()

        return queryset.select_related('level_type', 'video', 'partner').prefetch_related(
            'expected_learning_items',
            'prerequisites',
            'subjects',
            Prefetch('course_runs', queryset=CourseRunSerializer.prefetch_queryset(queryset=course_runs)),
            Prefetch('authoring_organizations', queryset=OrganizationSerializer.prefetch_queryset()),
            Prefetch('sponsoring_organizations', queryset=OrganizationSerializer.prefetch_queryset()),
        )

    def get_course_runs(self, course):
        return CourseRunSerializer(
            course.course_runs,
            many=True,
            context={
                'request': self.context.get('request'),
                'exclude_utm': self.context.get('exclude_utm'),
            }
        ).data

    def get_programs(self, obj):
        if self.context.get('include_deleted_programs'):
            eligible_programs = obj.programs.all()
        else:
            eligible_programs = obj.programs.exclude(status=ProgramStatus.Deleted)

        return NestedProgramSerializer(eligible_programs, many=True).data

    class Meta(CourseSerializer.Meta):
        model = Course
        fields = CourseSerializer.Meta.fields + ('programs',)


class CatalogCourseSerializer(CourseSerializer):
    """
    A CourseSerializer which only includes course runs that can be enrolled in
    immediately, are ongoing or yet to start, and appear on the marketing site
    (i.e., sellable runs that should appear in a catalog distributed to affiliates).
    """
    course_runs = serializers.SerializerMethodField()

    @classmethod
    def prefetch_queryset(cls, queryset=None, course_runs=None):
        """
        Similar to the CourseSerializer's prefetch_queryset, but prefetches a
        filtered CourseRun queryset.
        """
        queryset = queryset if queryset is not None else Course.objects.all()

        return queryset.select_related('level_type', 'video', 'partner').prefetch_related(
            'expected_learning_items',
            'prerequisites',
            'subjects',
            Prefetch('course_runs', queryset=CourseRunSerializer.prefetch_queryset(queryset=course_runs)),
            Prefetch('authoring_organizations', queryset=OrganizationSerializer.prefetch_queryset()),
            Prefetch('sponsoring_organizations', queryset=OrganizationSerializer.prefetch_queryset()),
        )

    def get_course_runs(self, course):
        return CourseRunSerializer(
            course.course_runs,
            many=True,
            context=self.context
        ).data


class ContainedCoursesSerializer(serializers.Serializer):
    """Serializer used to represent courses contained by a catalog."""
    courses = serializers.DictField(
        child=serializers.BooleanField(),
        help_text=_('Dictionary mapping course IDs to boolean values')
    )


class MinimalProgramCourseSerializer(MinimalCourseSerializer):
    """
    Serializer used to filter out excluded course runs in a course associated with the program.

    Notes:
        This is shared by both MinimalProgramSerializer and ProgramSerializer!
    """
    course_runs = serializers.SerializerMethodField()

    def get_course_runs(self, course):
        course_runs = self.context['course_runs']
        course_runs = [course_run for course_run in course_runs if course_run.course == course]

        if self.context.get('published_course_runs_only'):
            course_runs = [course_run for course_run in course_runs if course_run.status == CourseRunStatus.Published]

        serializer_class = MinimalCourseRunSerializer
        if self.context.get('use_full_course_serializer', False):
            serializer_class = CourseRunSerializer

        return serializer_class(
            course_runs,
            many=True,
            context={
                'request': self.context.get('request'),
                'exclude_utm': self.context.get('exclude_utm'),
            }
        ).data


class MinimalProgramSerializer(serializers.ModelSerializer):
    authoring_organizations = MinimalOrganizationSerializer(many=True)
    banner_image = StdImageSerializerField()
    courses = serializers.SerializerMethodField()
    type = serializers.SlugRelatedField(slug_field='name', queryset=ProgramType.objects.all())

    @classmethod
    def prefetch_queryset(cls):
        return Program.objects.all().select_related('type', 'partner').prefetch_related(
            'excluded_course_runs',
            # `type` is serialized by a third-party serializer. Providing this field name allows us to
            # prefetch `applicable_seat_types`, a m2m on `ProgramType`, through `type`, a foreign key to
            # `ProgramType` on `Program`.
            'type__applicable_seat_types',
            'authoring_organizations',
            Prefetch('courses', queryset=MinimalProgramCourseSerializer.prefetch_queryset()),
        )

    class Meta:
        model = Program
        fields = (
            'uuid', 'title', 'subtitle', 'type', 'status', 'marketing_slug', 'marketing_url', 'banner_image', 'hidden',
            'courses', 'authoring_organizations', 'card_image_url', 'is_program_eligible_for_one_click_purchase',
        )
        read_only_fields = ('uuid', 'marketing_url', 'banner_image')

    def get_courses(self, program):
        course_runs = list(program.course_runs)

        if self.context.get('marketable_enrollable_course_runs_with_archived'):
            marketable_enrollable_course_runs = set()
            for course in program.courses.all():
                marketable_enrollable_course_runs.update(course.course_runs.marketable().enrollable())
            course_runs = list(set(course_runs).intersection(marketable_enrollable_course_runs))

        if program.order_courses_by_start_date:
            courses = self.sort_courses(program, course_runs)
        else:
            courses = program.courses.all()

        course_serializer = MinimalProgramCourseSerializer(
            courses,
            many=True,
            context={
                'request': self.context.get('request'),
                'published_course_runs_only': self.context.get('published_course_runs_only'),
                'exclude_utm': self.context.get('exclude_utm'),
                'program': program,
                'course_runs': course_runs,
                'use_full_course_serializer': self.context.get('use_full_course_serializer', False),
            }
        )

        return course_serializer.data

    def sort_courses(self, program, course_runs):
        """
        Sorting by enrollment start then by course start yields a list ordered by course start, with
        ties broken by enrollment start. This works because Python sorting is stable: two objects with
        equal keys appear in the same order in sorted output as they appear in the input.

        Courses are only created if there's at least one course run belonging to that course, so
        course_runs should never be empty. If it is, key functions in this method attempting to find the
        min of an empty sequence will raise a ValueError.
        """

        def min_run_enrollment_start(course):
            # Enrollment starts may be empty. When this is the case, we make the same assumption as
            # the LMS: no enrollment_start is equivalent to (offset-aware) datetime.datetime.min.
            min_datetime = datetime.datetime.min.replace(tzinfo=pytz.UTC)

            # Course runs excluded from the program are excluded here, too.
            #
            # If this becomes a candidate for optimization in the future, be careful sorting null values
            # in the database. PostgreSQL and MySQL sort null values as if they are higher than non-null
            # values, while SQLite does the opposite.
            #
            # For more, refer to https://docs.djangoproject.com/en/1.10/ref/models/querysets/#latest.
            _course_runs = [course_run for course_run in course_runs if course_run.course == course]

            # Return early if we have no course runs since min() will fail.
            if not _course_runs:
                return min_datetime

            run = min(_course_runs, key=lambda run: run.enrollment_start or min_datetime)

            return run.enrollment_start or min_datetime

        def min_run_start(course):
            # Course starts may be empty. Since this means the course can't be started, missing course
            # start date is equivalent to (offset-aware) datetime.datetime.max.
            max_datetime = datetime.datetime.max.replace(tzinfo=pytz.UTC)

            _course_runs = [course_run for course_run in course_runs if course_run.course == course]

            # Return early if we have no course runs since min() will fail.
            if not _course_runs:
                return max_datetime

            run = min(_course_runs, key=lambda run: run.start or max_datetime)

            return run.start or max_datetime

        courses = list(program.courses.all())
        courses.sort(key=min_run_enrollment_start)
        courses.sort(key=min_run_start)

        return courses


class ProgramSerializer(MinimalProgramSerializer):
    authoring_organizations = OrganizationSerializer(many=True)
    video = VideoSerializer()
    expected_learning_items = serializers.SlugRelatedField(many=True, read_only=True, slug_field='value')
    faq = FAQSerializer(many=True)
    credit_backing_organizations = OrganizationSerializer(many=True)
    corporate_endorsements = CorporateEndorsementSerializer(many=True)
    job_outlook_items = serializers.SlugRelatedField(many=True, read_only=True, slug_field='value')
    individual_endorsements = EndorsementSerializer(many=True)
    languages = serializers.SlugRelatedField(
        many=True, read_only=True, slug_field='code',
        help_text=_('Languages that course runs in this program are offered in.'),
    )
    transcript_languages = serializers.SlugRelatedField(
        many=True, read_only=True, slug_field='code',
        help_text=_('Languages that course runs in this program have available transcripts in.'),
    )
    subjects = SubjectSerializer(many=True)
    staff = PersonSerializer(many=True)
    applicable_seat_types = serializers.SerializerMethodField()

    @classmethod
    def prefetch_queryset(cls):
        """
        Prefetch the related objects that will be serialized with a `Program`.

        We use Pefetch objects so that we can prefetch and select all the way down the
        chain of related fields from programs to course runs (i.e., we want control over
        the querysets that we're prefetching).
        """
        return Program.objects.all().select_related('type', 'video', 'partner').prefetch_related(
            'excluded_course_runs',
            'expected_learning_items',
            'faq',
            'job_outlook_items',
            # `type` is serialized by a third-party serializer. Providing this field name allows us to
            # prefetch `applicable_seat_types`, a m2m on `ProgramType`, through `type`, a foreign key to
            # `ProgramType` on `Program`.
            'type__applicable_seat_types',
            # We need the full Course prefetch here to get CourseRun information that methods on the Program
            # model iterate across (e.g. language). These fields aren't prefetched by the minimal Course serializer.
            Prefetch('courses', queryset=CourseSerializer.prefetch_queryset()),
            Prefetch('authoring_organizations', queryset=OrganizationSerializer.prefetch_queryset()),
            Prefetch('credit_backing_organizations', queryset=OrganizationSerializer.prefetch_queryset()),
            Prefetch('corporate_endorsements', queryset=CorporateEndorsementSerializer.prefetch_queryset()),
            Prefetch('individual_endorsements', queryset=EndorsementSerializer.prefetch_queryset()),
        )

    def get_applicable_seat_types(self, obj):
        return list(obj.type.applicable_seat_types.values_list('slug', flat=True))

    class Meta(MinimalProgramSerializer.Meta):
        model = Program
        fields = MinimalProgramSerializer.Meta.fields + (
            'overview', 'weeks_to_complete', 'weeks_to_complete_min', 'weeks_to_complete_max',
            'min_hours_effort_per_week', 'max_hours_effort_per_week', 'video', 'expected_learning_items',
            'faq', 'credit_backing_organizations', 'corporate_endorsements', 'job_outlook_items',
            'individual_endorsements', 'languages', 'transcript_languages', 'subjects', 'price_ranges',
            'staff', 'credit_redemption_overview', 'applicable_seat_types'
        )


class ProgramTypeSerializer(serializers.ModelSerializer):
    """ Serializer for the Program Types. """
    applicable_seat_types = serializers.SlugRelatedField(many=True, read_only=True, slug_field='slug')
    logo_image = StdImageSerializerField()

    @classmethod
    def prefetch_queryset(cls, queryset):
        return queryset.prefetch_related('applicable_seat_types')

    class Meta:
        model = ProgramType
        fields = ('name', 'logo_image', 'applicable_seat_types', 'slug',)


class AffiliateWindowSerializer(serializers.ModelSerializer):
    """ Serializer for Affiliate Window product feeds. """

    # We use a hardcoded value since it is determined by Affiliate Window's taxonomy.
    CATEGORY = 'Other Experiences'

    pid = serializers.SerializerMethodField()
    name = serializers.CharField(source='course_run.title')
    desc = serializers.CharField(source='course_run.short_description')
    purl = serializers.CharField(source='course_run.marketing_url')
    imgurl = serializers.CharField(source='course_run.card_image_url')
    category = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()

    class Meta:
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
    expected_learning_items = serializers.SerializerMethodField()
    course_key = serializers.SlugRelatedField(read_only=True, source='course', slug_field='key')
    image = ImageField(read_only=True, source='card_image_url')

    class Meta:
        model = CourseRun
        fields = (
            'key', 'title', 'short_description', 'full_description', 'level_type', 'subjects', 'prerequisites',
            'start', 'end', 'enrollment_start', 'enrollment_end', 'announcement', 'seats', 'content_language',
            'transcript_languages', 'staff', 'pacing_type', 'min_effort', 'max_effort', 'course_key',
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

        for credit_attr in seats['credit']:
            seats['credit'][credit_attr] = ','.join([str(e) for e in seats['credit'][credit_attr]])

        return seats

    def get_owners(self, obj):
        return ','.join([owner.key for owner in obj.course.authoring_organizations.all()])

    def get_sponsors(self, obj):
        return ','.join([sponsor.key for sponsor in obj.course.sponsoring_organizations.all()])

    def get_subjects(self, obj):
        return ','.join([subject.name for subject in obj.course.subjects.all()])

    def get_prerequisites(self, obj):
        return ','.join([prerequisite.name for prerequisite in obj.course.prerequisites.all()])

    def get_expected_learning_items(self, obj):
        return ','.join(
            [expected_learning_item.value for expected_learning_item in obj.course.expected_learning_items.all()]
        )


class QueryFacetFieldSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    narrow_url = serializers.SerializerMethodField()

    def get_paginate_by_param(self):
        """
        Returns the ``paginate_by_param`` for the (root) view paginator class.
        This is needed in order to remove the query parameter from faceted
        narrow urls.

        If using a custom pagination class, this class attribute needs to
        be set manually.
        """
        # NOTE (CCB): We use PageNumberPagination. See drf-haystack's FacetFieldSerializer.get_paginate_by_param
        # for complete code that is applicable to any pagination class.
        pagination_class = self.context['view'].pagination_class
        return pagination_class.page_query_param

    def get_narrow_url(self, instance):
        """
        Return a link suitable for narrowing on the current item.

        Since we don't have any means of getting the ``view name`` from here,
        we can only return relative paths.
        """
        field = instance['field']
        request = self.context['request']
        query_params = request.GET.copy()

        # Never keep the page query parameter in narrowing urls.
        # It will raise a NotFound exception when trying to paginate a narrowed queryset.
        page_query_param = self.get_paginate_by_param()
        if page_query_param in query_params:
            del query_params[page_query_param]

        selected_facets = set(query_params.pop('selected_query_facets', []))
        selected_facets.add(field)
        query_params.setlist('selected_query_facets', sorted(selected_facets))

        path = '{path}?{query}'.format(path=request.path_info, query=query_params.urlencode())
        url = request.build_absolute_uri(path)
        return serializers.Hyperlink(url, 'narrow-url')


class BaseHaystackFacetSerializer(HaystackFacetSerializer):
    _abstract = True

    def get_fields(self):
        query_facet_counts = self.instance.pop('queries', {})

        field_mapping = super(BaseHaystackFacetSerializer, self).get_fields()

        query_data = self.format_query_facet_data(query_facet_counts)

        field_mapping['queries'] = DictField(query_data, child=QueryFacetFieldSerializer(), required=False)

        if self.serialize_objects:
            field_mapping.move_to_end('objects')

        self.instance['queries'] = query_data

        return field_mapping

    def format_query_facet_data(self, query_facet_counts):
        query_data = {}
        for field, options in getattr(self.Meta, 'field_queries', {}).items():  # pylint: disable=no-member
            count = query_facet_counts.get(field, 0)
            if count:
                query_data[field] = {
                    'field': field,
                    'options': options,
                    'count': count,
                }
        return query_data


class CourseSearchSerializer(HaystackSerializer):
    content_type = serializers.CharField(source='model_name')

    class Meta:
        field_aliases = COMMON_SEARCH_FIELD_ALIASES
        fields = ('key', 'title', 'short_description', 'full_description', 'text', 'aggregation_key',)
        ignore_fields = COMMON_IGNORED_FIELDS
        index_classes = [CourseIndex]


class CourseFacetSerializer(BaseHaystackFacetSerializer):
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
    availability = serializers.SerializerMethodField()

    def get_availability(self, result):
        return result.object.availability

    class Meta:
        field_aliases = COMMON_SEARCH_FIELD_ALIASES
        fields = COURSE_RUN_SEARCH_FIELDS
        ignore_fields = COMMON_IGNORED_FIELDS
        index_classes = [CourseRunIndex]


class CourseRunFacetSerializer(BaseHaystackFacetSerializer):
    serialize_objects = True

    class Meta:
        field_aliases = COMMON_SEARCH_FIELD_ALIASES
        field_options = COURSE_RUN_FACET_FIELD_OPTIONS
        field_queries = COURSE_RUN_FACET_FIELD_QUERIES
        ignore_fields = COMMON_IGNORED_FIELDS


class ProgramSearchSerializer(HaystackSerializer):
    authoring_organizations = serializers.SerializerMethodField()

    def get_authoring_organizations(self, program):
        organizations = program.authoring_organization_bodies
        return [json.loads(organization) for organization in organizations] if organizations else []

    class Meta:
        field_aliases = COMMON_SEARCH_FIELD_ALIASES
        field_options = PROGRAM_FACET_FIELD_OPTIONS
        fields = PROGRAM_SEARCH_FIELDS
        ignore_fields = COMMON_IGNORED_FIELDS
        index_classes = [ProgramIndex]


class ProgramFacetSerializer(BaseHaystackFacetSerializer):
    serialize_objects = True

    class Meta:
        field_aliases = COMMON_SEARCH_FIELD_ALIASES
        field_options = PROGRAM_FACET_FIELD_OPTIONS
        fields = PROGRAM_FACET_FIELDS
        ignore_fields = COMMON_IGNORED_FIELDS
        index_classes = [ProgramIndex]


class AggregateSearchSerializer(HaystackSerializer):
    class Meta:
        field_aliases = COMMON_SEARCH_FIELD_ALIASES
        fields = COURSE_RUN_SEARCH_FIELDS + PROGRAM_SEARCH_FIELDS
        ignore_fields = COMMON_IGNORED_FIELDS
        serializers = {
            CourseRunIndex: CourseRunSearchSerializer,
            CourseIndex: CourseSearchSerializer,
            ProgramIndex: ProgramSearchSerializer,
        }


class TypeaheadBaseSearchSerializer(serializers.Serializer):
    orgs = serializers.SerializerMethodField()
    title = serializers.CharField()
    marketing_url = serializers.CharField()

    def get_orgs(self, result):
        authoring_organizations = [json.loads(org) for org in result.authoring_organization_bodies]
        return [org['key'] for org in authoring_organizations]


class TypeaheadCourseRunSearchSerializer(TypeaheadBaseSearchSerializer):
    key = serializers.CharField()


class TypeaheadProgramSearchSerializer(TypeaheadBaseSearchSerializer):
    uuid = serializers.CharField()
    type = serializers.CharField()


class TypeaheadSearchSerializer(serializers.Serializer):
    course_runs = TypeaheadCourseRunSearchSerializer(many=True)
    programs = TypeaheadProgramSearchSerializer(many=True)


class AggregateFacetSearchSerializer(BaseHaystackFacetSerializer):
    serialize_objects = True

    class Meta:
        field_aliases = COMMON_SEARCH_FIELD_ALIASES
        field_options = {**COURSE_RUN_FACET_FIELD_OPTIONS, **PROGRAM_FACET_FIELD_OPTIONS}
        field_queries = COURSE_RUN_FACET_FIELD_QUERIES
        ignore_fields = COMMON_IGNORED_FIELDS
        serializers = {
            CourseRunIndex: CourseRunFacetSerializer,
            CourseIndex: CourseFacetSerializer,
            ProgramIndex: ProgramFacetSerializer,
        }
