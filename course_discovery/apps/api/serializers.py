# pylint: disable=abstract-method
import json
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.utils.translation import ugettext_lazy as _
from drf_haystack.serializers import HaystackSerializer, HaystackFacetSerializer
from rest_framework import serializers
from rest_framework.fields import DictField
from taggit_serializer.serializers import TagListSerializerField, TaggitSerializer

from course_discovery.apps.api.fields import StdImageSerializerField, ImageField
from course_discovery.apps.catalogs.models import Catalog
from course_discovery.apps.course_metadata.models import (
    Course, CourseRun, Image, Organization, Person, Prerequisite, Seat, Subject, Video, Program, ProgramType, FAQ,
    CorporateEndorsement, Endorsement
)
from course_discovery.apps.course_metadata.search_indexes import CourseIndex, CourseRunIndex, ProgramIndex

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
    'text', 'key', 'title', 'short_description', 'full_description', 'start', 'end', 'enrollment_start',
    'enrollment_end', 'pacing_type', 'language', 'transcript_languages', 'marketing_url', 'content_type', 'org',
    'number', 'seat_types', 'image_url', 'type', 'level_type', 'availability',
)

PROGRAM_FACET_FIELD_OPTIONS = {
    'category': {},
    'status': {},
    'type': {},
}

BASE_PROGRAM_FIELDS = (
    'text', 'uuid', 'title', 'subtitle', 'type', 'marketing_url', 'content_type', 'status', 'card_image_url',
)

PROGRAM_SEARCH_FIELDS = BASE_PROGRAM_FIELDS + ('authoring_organizations',)
PROGRAM_FACET_FIELDS = BASE_PROGRAM_FIELDS + ('organizations',)


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


class FAQSerializer(serializers.ModelSerializer):
    """Serializer for the ``FAQ`` model."""

    class Meta(object):
        model = FAQ
        fields = ('question', 'answer',)


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


class PersonSerializer(serializers.ModelSerializer):
    """Serializer for the ``Person`` model."""

    class Meta(object):
        model = Person
        fields = ('uuid', 'given_name', 'family_name', 'bio', 'profile_image_url', 'slug',)


class EndorsementSerializer(serializers.ModelSerializer):
    """Serializer for the ``Endorsement`` model."""
    endorser = PersonSerializer()

    class Meta(object):
        model = Endorsement
        fields = ('endorser', 'quote',)


class CorporateEndorsementSerializer(serializers.ModelSerializer):
    """Serializer for the ``CorporateEndorsement`` model."""
    image = ImageSerializer()
    individual_endorsements = EndorsementSerializer(many=True)

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

    class Meta(object):
        model = Seat
        fields = ('type', 'price', 'currency', 'upgrade_deadline', 'credit_provider', 'credit_hours',)


class OrganizationSerializer(TaggitSerializer, serializers.ModelSerializer):
    """Serializer for the ``Organization`` model."""
    tags = TagListSerializerField()

    class Meta(object):
        model = Organization
        fields = ('key', 'name', 'description', 'homepage_url', 'tags',)


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


class CourseRunSerializer(TimestampModelSerializer):
    """Serializer for the ``CourseRun`` model."""
    course = serializers.SlugRelatedField(read_only=True, slug_field='key')
    content_language = serializers.SlugRelatedField(
        read_only=True, slug_field='code', source='language',
        help_text=_('Language in which the course is administered')
    )
    transcript_languages = serializers.SlugRelatedField(many=True, read_only=True, slug_field='code')
    image = ImageField(read_only=True, source='card_image_url')
    video = VideoSerializer()
    seats = SeatSerializer(many=True)
    instructors = serializers.SerializerMethodField(help_text='This field is deprecated. Use staff.')
    staff = PersonSerializer(many=True)
    marketing_url = serializers.SerializerMethodField()
    level_type = serializers.SlugRelatedField(read_only=True, slug_field='name')

    class Meta(object):
        model = CourseRun
        fields = (
            'course', 'key', 'title', 'short_description', 'full_description', 'start', 'end',
            'enrollment_start', 'enrollment_end', 'announcement', 'image', 'video', 'seats',
            'content_language', 'transcript_languages', 'instructors', 'staff',
            'pacing_type', 'min_effort', 'max_effort', 'modified', 'marketing_url', 'level_type', 'availability',
        )

    def get_marketing_url(self, obj):
        return get_marketing_url_for_user(self.context['request'].user, obj.marketing_url)

    def get_instructors(self, obj):  # pylint: disable=unused-argument
        return []


class CourseRunWithProgramsSerializer(CourseRunSerializer):
    """A ``CourseRunSerializer`` which includes programs derived from parent course."""
    programs = NestedProgramSerializer(many=True)

    class Meta(CourseRunSerializer.Meta):
        model = CourseRun
        fields = CourseRunSerializer.Meta.fields + ('programs', )


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
    image = ImageField(read_only=True, source='card_image_url')
    video = VideoSerializer()
    owners = OrganizationSerializer(many=True, source='authoring_organizations')
    sponsors = OrganizationSerializer(many=True, source='sponsoring_organizations')
    course_runs = CourseRunSerializer(many=True)
    marketing_url = serializers.SerializerMethodField()

    class Meta(object):
        model = Course
        fields = (
            'key', 'title', 'short_description', 'full_description', 'level_type', 'subjects', 'prerequisites',
            'expected_learning_items', 'image', 'video', 'owners', 'sponsors', 'modified', 'course_runs',
            'marketing_url',
        )

    def get_marketing_url(self, obj):
        return get_marketing_url_for_user(self.context['request'].user, obj.marketing_url)


class CourseWithProgramsSerializer(CourseSerializer):
    """A ``CourseSerializer`` which includes programs."""
    programs = NestedProgramSerializer(many=True)

    class Meta(CourseSerializer.Meta):
        model = Course
        fields = CourseSerializer.Meta.fields + ('programs', )


class CourseSerializerExcludingClosedRuns(CourseSerializer):
    """A ``CourseSerializer`` which only includes active course runs, as determined by ``CourseQuerySet``."""
    course_runs = CourseRunSerializer(many=True, source='active_course_runs')


class ContainedCoursesSerializer(serializers.Serializer):
    """Serializer used to represent courses contained by a catalog."""
    courses = serializers.DictField(
        child=serializers.BooleanField(),
        help_text=_('Dictionary mapping course IDs to boolean values')
    )


class ProgramCourseSerializer(CourseSerializer):
    """Serializer used to filter out excluded course runs in a course associated with the program"""
    course_runs = serializers.SerializerMethodField()

    def get_course_runs(self, course):
        program = self.context['program']
        course_runs = program.course_runs.filter(course=course)
        return CourseRunSerializer(
            course_runs,
            many=True,
            context={'request': self.context.get('request')}
        ).data


class ProgramSerializer(serializers.ModelSerializer):
    courses = serializers.SerializerMethodField()
    authoring_organizations = OrganizationSerializer(many=True)
    type = serializers.SlugRelatedField(slug_field='name', queryset=ProgramType.objects.all())
    banner_image = StdImageSerializerField()
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

    def get_courses(self, program):
        course_serializer = ProgramCourseSerializer(
            program.courses,
            many=True,
            context={
                'request': self.context.get('request'),
                'program': program
            }
        )
        return course_serializer.data

    class Meta:
        model = Program
        fields = (
            'uuid', 'title', 'subtitle', 'type', 'status', 'marketing_slug', 'marketing_url', 'courses',
            'overview', 'weeks_to_complete', 'min_hours_effort_per_week', 'max_hours_effort_per_week',
            'authoring_organizations', 'banner_image', 'banner_image_url', 'card_image_url', 'video',
            'expected_learning_items', 'faq', 'credit_backing_organizations', 'corporate_endorsements',
            'job_outlook_items', 'individual_endorsements', 'languages', 'transcript_languages', 'subjects',
            'price_ranges', 'staff', 'credit_redemption_overview'
        )
        read_only_fields = ('uuid', 'marketing_url', 'banner_image')


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
    image = ImageField(read_only=True, source='card_image_url')

    class Meta(object):
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

        for credit_attr in seats['credit'].keys():
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

    def get_level_type(self, obj):
        return obj.course.level_type

    def get_course_key(self, obj):
        return obj.course.key


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
        return serializers.Hyperlink(url, name='narrow-url')


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
        fields = ('key', 'title', 'short_description', 'full_description', 'text',)
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
