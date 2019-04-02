# pylint: disable=abstract-method,no-member
import datetime
import json
from collections import OrderedDict
from operator import attrgetter
from urllib.parse import urlencode
from uuid import uuid4

import pytz
import waffle
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.db.models.query import Prefetch
from django.utils.text import slugify
from django.utils.translation import ugettext_lazy as _
from drf_dynamic_fields import DynamicFieldsMixin
from drf_haystack.serializers import HaystackFacetSerializer, HaystackSerializer, HaystackSerializerMixin
from opaque_keys.edx.locator import CourseLocator
from rest_framework import serializers
from rest_framework.fields import CreateOnlyDefault, DictField, UUIDField
from rest_framework.metadata import SimpleMetadata
from taggit_serializer.serializers import TaggitSerializer, TagListSerializerField

from course_discovery.apps.api.fields import ImageField, StdImageSerializerField
from course_discovery.apps.catalogs.models import Catalog
from course_discovery.apps.core.api_client.lms import LMSAPIClient
from course_discovery.apps.course_metadata import search_indexes
from course_discovery.apps.course_metadata.choices import CourseRunStatus, ProgramStatus
from course_discovery.apps.course_metadata.models import (
    FAQ, AdditionalPromoArea, CorporateEndorsement, Course, CourseEntitlement, CourseRun, Curriculum,
    CurriculumCourseMembership, CurriculumProgramMembership, Degree, DegreeCost, DegreeDeadline, Endorsement,
    IconTextPairing, Image, LevelType, Organization, Pathway, Person, PersonAreaOfExpertise, PersonSocialNetwork,
    Position, Prerequisite, Program, ProgramType, Ranking, Seat, SeatType, Subject, Topic, Video
)
from course_discovery.apps.course_metadata.utils import parse_course_key_fragment
from course_discovery.apps.ietf_language_tags.models import LanguageTag
from course_discovery.apps.publisher.models import CourseRun as PublisherCourseRun
from course_discovery.apps.publisher.studio_api_utils import StudioAPI

User = get_user_model()

COMMON_IGNORED_FIELDS = ('text',)
COMMON_SEARCH_FIELD_ALIASES = {'q': 'text'}
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


def get_marketing_url_for_user(partner, user, marketing_url, exclude_utm=False):
    """
    Return the given marketing URL with affiliate query parameters for the user.

    Arguments:
        partner (Partner): Partner instance containing information.
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
            'utm_source': get_utm_source_for_user(partner, user),
            'utm_medium': user.referral_tracking_id,
        })
        return '{url}?{params}'.format(url=marketing_url, params=params)


def get_lms_course_url_for_archived(partner, course_key):
    """
    Return the LMS course home URL for archived course runs.

    Arguments:
        partner (Partner): Partner instance containing information.
        course_key (String): course key string

    Returns:
        str | None
    """
    lms_url = partner.lms_url
    if not course_key or not lms_url:
        return None

    return '{lms_url}/courses/{course_key}/course/'.format(lms_url=lms_url, course_key=course_key)


def get_utm_source_for_user(partner, user):
    """
    Return the utm source for the user.

    Arguments:
        partner (Partner): Partner instance containing information.
        user (User): Used to construct UTM query parameters.

    Returns:
        str: username and company name slugified and combined together.
    """
    utm_source = user.username
    # If use_company_name_as_utm_source_value is enabled and lms_url value is set then
    # use company name from API Access Request as utm_source.
    if waffle.switch_is_active('use_company_name_as_utm_source_value') and partner.lms_url:
        lms = LMSAPIClient(partner.site)

        # This result is not being used to determine access. It is only being
        # used to create an alternative UTM code parsed from the result.
        api_access_request = lms.get_api_access_request(user)

        if api_access_request:
            utm_source = '{} {}'.format(utm_source, api_access_request['company_name'])

    return slugify(utm_source)


class MetadataWithRelatedChoices(SimpleMetadata):
    """ A version of the normal DRF metadata class that also returns choices for RelatedFields """

    def determine_metadata(self, request, view):
        self.view = view  # pylint: disable=attribute-defined-outside-init
        return super().determine_metadata(request, view)

    def get_field_info(self, field):
        info = super().get_field_info(field)

        in_whitelist = False
        if hasattr(self.view, 'metadata_related_choices_whitelist'):
            in_whitelist = field.field_name in self.view.metadata_related_choices_whitelist

        # The normal metadata class excludes RelatedFields, but we want them! So we do the same thing the normal
        # class does, but without the RelatedField check.
        if in_whitelist and not info.get('read_only') and hasattr(field, 'choices'):
            info['choices'] = [
                {
                    'value': choice_value,
                    'display_name': choice_name,
                }
                for choice_value, choice_name in field.choices.items()
            ]

        return info


class TimestampModelSerializer(serializers.ModelSerializer):
    """Serializer for timestamped models."""
    modified = serializers.DateTimeField(required=False)


class ContentTypeSerializer(serializers.Serializer):
    """Serializer for retrieving the type of content. Useful in views returning multiple serialized models."""
    content_type = serializers.SerializerMethodField()

    def get_content_type(self, obj):
        return obj._meta.model_name

    class Meta(object):
        fields = ('content_type',)


class NamedModelSerializer(serializers.ModelSerializer):
    """Serializer for models inheriting from ``AbstractNamedModel``."""
    name = serializers.CharField()

    class Meta(object):
        fields = ('name',)


class TitleDescriptionSerializer(serializers.ModelSerializer):
    """Serializer for models inheriting from ``AbstractTitleDescription``."""
    class Meta(object):
        fields = ('title', 'description',)


class AdditionalPromoAreaSerializer(TitleDescriptionSerializer):
    """Serializer for AdditionalPromoArea """
    class Meta(TitleDescriptionSerializer.Meta):
        model = AdditionalPromoArea


class FAQSerializer(serializers.ModelSerializer):
    """Serializer for the ``FAQ`` model."""

    class Meta(object):
        model = FAQ
        fields = ('question', 'answer',)


class SubjectSerializer(serializers.ModelSerializer):
    """Serializer for the ``Subject`` model."""

    @classmethod
    def prefetch_queryset(cls):
        return Subject.objects.all().prefetch_related('translations')

    class Meta(object):
        model = Subject
        fields = ('name', 'subtitle', 'description', 'banner_image_url', 'card_image_url', 'slug', 'uuid')

    @property
    def choices(self):
        # choices shows the possible values via HTTP's OPTIONS verb
        return OrderedDict(sorted([(x.slug, x.name) for x in Subject.objects.all()], key=lambda x: x[1]))


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
    organization_marketing_url = serializers.SerializerMethodField()
    # Order organization by key so that frontends will display dropdowns of organization choices that way
    organization = serializers.PrimaryKeyRelatedField(allow_null=True, write_only=True, required=False,
                                                      queryset=Organization.objects.all().order_by('key'))

    class Meta(object):
        model = Position
        fields = (
            'title', 'organization_name', 'organization', 'organization_id', 'organization_override',
            'organization_marketing_url',
        )
        extra_kwargs = {
            'organization': {'write_only': True}
        }

    def get_organization_marketing_url(self, obj):
        if obj.organization:
            return obj.organization.marketing_url


class MinimalOrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ('uuid', 'key', 'name',)


class OrganizationSerializer(TaggitSerializer, MinimalOrganizationSerializer):
    """Serializer for the ``Organization`` model."""
    tags = TagListSerializerField()

    @classmethod
    def prefetch_queryset(cls, partner):
        return Organization.objects.filter(partner=partner).select_related('partner').prefetch_related('tags')

    class Meta(MinimalOrganizationSerializer.Meta):
        fields = MinimalOrganizationSerializer.Meta.fields + (
            'certificate_logo_image_url', 'description', 'homepage_url', 'tags', 'logo_image_url', 'marketing_url',
        )


class MinimalPersonSerializer(serializers.ModelSerializer):
    """
    Minimal serializer for the ``Person`` model.
    """
    position = PositionSerializer(required=False)
    profile_image_url = serializers.SerializerMethodField()
    profile_image = StdImageSerializerField(required=False)
    works = serializers.SerializerMethodField()
    urls = serializers.SerializerMethodField()
    urls_detailed = serializers.SerializerMethodField()
    areas_of_expertise = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()

    @classmethod
    def prefetch_queryset(cls):
        return Person.objects.all().select_related(
            'position__organization'
        ).prefetch_related(
            'person_networks',
            'areas_of_expertise',
            'position__organization__partner',
        )

    class Meta(object):
        model = Person
        fields = (
            'uuid', 'salutation', 'given_name', 'family_name', 'bio', 'slug', 'position', 'areas_of_expertise',
            'profile_image', 'partner', 'works', 'urls', 'urls_detailed', 'email', 'profile_image_url', 'major_works',
            'published',
        )
        extra_kwargs = {
            'partner': {'write_only': True}
        }

    def get_works(self, _obj):
        # For historical reasons, we provide this field. But now we store works as one giant text field (major_works)
        return []

    def get_social_network_url(self, url_type, obj):
        # filter() isn't used to avoid discarding prefetched results.
        social_networks = [network for network in obj.person_networks.all() if network.type == url_type]

        if social_networks:
            return social_networks[0].url

    def get_profile_image_url(self, obj):
        return obj.get_profile_image_url

    def get_urls(self, obj):
        return {
            PersonSocialNetwork.FACEBOOK: self.get_social_network_url(PersonSocialNetwork.FACEBOOK, obj),
            PersonSocialNetwork.TWITTER: self.get_social_network_url(PersonSocialNetwork.TWITTER, obj),
            PersonSocialNetwork.BLOG: self.get_social_network_url(PersonSocialNetwork.BLOG, obj),
        }

    def get_urls_detailed(self, obj):
        """
        Sort the person_networks with sorted rather than order_by to avoid
        additional calls to the database
        """
        return [{
            'id': network.id,
            'type': network.type,
            'title': network.title,
            'display_title': network.display_title,
            'url': network.url,
        } for network in sorted(obj.person_networks.all(), key=attrgetter('id'))]

    def get_areas_of_expertise(self, obj):
        """
        Sort the areas_of_expertise with sorted rather than order_by to avoid
        additional calls to the database
        """
        return [{
            'id': area_of_expertise.id,
            'value': area_of_expertise.value,
        } for area_of_expertise in sorted(obj.areas_of_expertise.all(), key=attrgetter('id'))]

    def get_email(self, _obj):
        # We are removing this field so this is to not break any APIs
        return None


class PersonSerializer(MinimalPersonSerializer):
    """Full serializer for the ``Person`` model."""

    def validate(self, data):
        validated_data = super(PersonSerializer, self).validate(data)
        validated_data['urls_detailed'] = self.initial_data.get('urls_detailed', [])
        validated_data['areas_of_expertise'] = self.initial_data.get('areas_of_expertise', [])
        return validated_data

    def create(self, validated_data):
        position_data = validated_data.pop('position')
        urls_detailed_data = validated_data.pop('urls_detailed')
        areas_of_expertise_data = validated_data.pop('areas_of_expertise')

        person = Person.objects.create(**validated_data)
        Position.objects.create(person=person, **position_data)

        person_social_networks = []
        for url_detailed in urls_detailed_data:
            person_social_networks.append(PersonSocialNetwork(
                person=person, type=url_detailed['type'], title=url_detailed['title'], url=url_detailed['url'],
            ))
        PersonSocialNetwork.objects.bulk_create(person_social_networks)

        areas_of_expertise = []
        for area_of_expertise in areas_of_expertise_data:
            areas_of_expertise.append(PersonAreaOfExpertise(person=person, value=area_of_expertise['value'],))
        PersonAreaOfExpertise.objects.bulk_create(areas_of_expertise)

        return person

    def update(self, instance, validated_data):
        position_data = validated_data.pop('position')
        urls_detailed_data = validated_data.pop('urls_detailed')
        areas_of_expertise_data = validated_data.pop('areas_of_expertise')

        Position.objects.update_or_create(person=instance, defaults=position_data)

        active_social_network_ids = [url_detailed['id'] for url_detailed in urls_detailed_data]
        for network in PersonSocialNetwork.objects.filter(person=instance):
            if network.id not in active_social_network_ids:
                network.delete()

        for url_detailed in urls_detailed_data:
            defaults = {
                'url': url_detailed['url'],
                'type': url_detailed['type'],
                'title': url_detailed['title'],
            }

            if url_detailed['id']:
                PersonSocialNetwork.objects.update_or_create(
                    person=instance, id=url_detailed['id'], defaults=defaults,
                )
            else:
                PersonSocialNetwork.objects.create(person=instance, **defaults)

        active_area_of_expertise_ids = [area_of_expertise['id'] for area_of_expertise in areas_of_expertise_data]
        for area_of_expertise in PersonAreaOfExpertise.objects.filter(person=instance):
            if area_of_expertise.id not in active_area_of_expertise_ids:
                area_of_expertise.delete()

        for area_of_expertise in areas_of_expertise_data:
            defaults = {'value': area_of_expertise['value']}
            if area_of_expertise['id']:
                PersonAreaOfExpertise.objects.update_or_create(
                    person=instance, id=area_of_expertise['id'], defaults=defaults,
                )
            else:
                PersonAreaOfExpertise.objects.create(person=instance, **defaults)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        return instance


class EndorsementSerializer(serializers.ModelSerializer):
    """Serializer for the ``Endorsement`` model."""
    endorser = MinimalPersonSerializer()

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
    bulk_sku = serializers.CharField()

    @classmethod
    def prefetch_queryset(cls):
        return Seat.everything.all().select_related('currency')

    class Meta(object):
        model = Seat
        fields = ('type', 'price', 'currency', 'upgrade_deadline', 'credit_provider', 'credit_hours', 'sku', 'bulk_sku')


class CourseEntitlementSerializer(serializers.ModelSerializer):
    """Serializer for the ``CourseEntitlement`` model."""
    price = serializers.DecimalField(
        decimal_places=CourseEntitlement.PRICE_FIELD_CONFIG['decimal_places'],
        max_digits=CourseEntitlement.PRICE_FIELD_CONFIG['max_digits']
    )
    currency = serializers.SlugRelatedField(read_only=True, slug_field='code')
    sku = serializers.CharField()
    mode = serializers.SlugRelatedField(slug_field='slug', queryset=SeatType.objects.all().order_by('name'))
    expires = serializers.DateTimeField()

    @classmethod
    def prefetch_queryset(cls):
        return CourseEntitlement.everything.all().select_related('currency', 'mode')

    class Meta(object):
        model = CourseEntitlement
        fields = ('mode', 'price', 'currency', 'sku', 'expires')


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
    the basic details of the Program and none of the details about its related entities, aside from the number
    of courses in the program.
    """
    type = serializers.SlugRelatedField(slug_field='name', queryset=ProgramType.objects.all())
    number_of_courses = serializers.SerializerMethodField()

    class Meta:
        model = Program
        fields = ('uuid', 'title', 'type', 'marketing_slug', 'marketing_url', 'number_of_courses',)
        read_only_fields = ('uuid', 'marketing_url', 'number_of_courses',)

    def get_number_of_courses(self, obj):
        return obj.courses.count()


class MinimalPublisherCourseRunSerializer(TimestampModelSerializer):
    course = serializers.SerializerMethodField()
    title = serializers.SerializerMethodField()

    class Meta:
        model = PublisherCourseRun
        fields = ('lms_course_id', 'course', 'title', 'start', 'end', 'pacing_type',)

    def get_course(self, obj):
        return obj.course.key

    def get_title(self, obj):
        return obj.title_override or obj.course.title


class MinimalCourseRunSerializer(DynamicFieldsMixin, TimestampModelSerializer):
    image = ImageField(read_only=True, source='image_url')
    marketing_url = serializers.SerializerMethodField()
    seats = SeatSerializer(required=False, many=True)
    key = serializers.CharField(required=False)
    title = serializers.CharField(required=False)
    short_description = serializers.CharField(required=False, allow_blank=True)
    start = serializers.DateTimeField(required=True)  # required so we can craft key number from it
    end = serializers.DateTimeField(required=True)  # required by studio

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
        include_archived = self.context.get('include_archived')
        now = datetime.datetime.now(pytz.UTC)
        if include_archived and obj.end and obj.end <= now:
            marketing_url = get_lms_course_url_for_archived(obj.course.partner, obj.key)
        else:
            marketing_url = get_marketing_url_for_user(
                obj.course.partner,
                self.context['request'].user,
                obj.marketing_url,
                exclude_utm=self.context.get('exclude_utm')
            )

        return marketing_url

    def ensure_key(self, data):
        course = data['course']  # required

        # There are two paths here - either the key was provided or start date was and we generate key from that.
        # We prefer the start date path and only allow certain organizations to provide a key.

        allow_key_override = False
        for organization in course.authoring_organizations.all():
            try:
                # This flag is oddly named - it's because creating an instance in studio generated the key in old
                # publisher. Nowadays, we always push to studio and allow overriding the key if that's what the org
                # really wants.
                if not organization.organization_extension.auto_create_in_studio:
                    allow_key_override = True
                    break
            except ObjectDoesNotExist:
                pass  # no organization extension

        if allow_key_override and 'key' in data:
            return

        # Now, override whatever value for key was provided by looking at the start date
        start = data['start']  # required
        org, number = parse_course_key_fragment(course.key)
        run = StudioAPI.calculate_course_run_key_run_value(number, start)
        key = CourseLocator(org=org, course=number, run=run)
        data['key'] = str(key)

    def validate(self, data):
        start = data.get('start', self.instance.start if self.instance else None)
        end = data.get('end', self.instance.end if self.instance else None)

        if start and end and start > end:
            raise serializers.ValidationError({'start': _('Start date cannot be after the End date')})

        if not self.instance:  # if we're creating an object, we need to make sure to generate a key
            self.ensure_key(data)
        elif 'key' in data and self.instance.key != data['key']:
            raise serializers.ValidationError({'key': _('Key cannot be changed')})

        return super().validate(data)


class CourseRunSerializer(MinimalCourseRunSerializer):
    """Serializer for the ``CourseRun`` model."""
    course = serializers.SlugRelatedField(required=True, slug_field='key', queryset=Course.objects.all())
    content_language = serializers.SlugRelatedField(
        required=False, allow_null=True, slug_field='code', source='language', queryset=LanguageTag.objects.all(),
        help_text=_('Language in which the course is administered')
    )
    transcript_languages = serializers.SlugRelatedField(
        required=False, many=True, slug_field='code', queryset=LanguageTag.objects.all()
    )
    video = VideoSerializer(required=False, allow_null=True, source='get_video')
    instructors = serializers.SerializerMethodField(help_text='This field is deprecated. Use staff.')
    staff = MinimalPersonSerializer(required=False, many=True)  # if you change, change to_internal_value too
    level_type = serializers.SlugRelatedField(
        required=False,
        allow_null=True,
        slug_field='name',
        queryset=LevelType.objects.all()
    )
    full_description = serializers.CharField(required=False, allow_blank=True)
    outcome = serializers.CharField(required=False, allow_blank=True)

    @classmethod
    def prefetch_queryset(cls, queryset=None):
        queryset = super().prefetch_queryset(queryset=queryset)

        return queryset.select_related('language', 'video').prefetch_related(
            'course__level_type',
            'transcript_languages',
            'video__image',
            Prefetch('staff', queryset=MinimalPersonSerializer.prefetch_queryset()),
        )

    class Meta(MinimalCourseRunSerializer.Meta):
        fields = MinimalCourseRunSerializer.Meta.fields + (
            'course', 'full_description', 'announcement', 'video', 'seats', 'content_language', 'license', 'outcome',
            'transcript_languages', 'instructors', 'staff', 'min_effort', 'max_effort', 'weeks_to_complete', 'modified',
            'level_type', 'availability', 'mobile_available', 'hidden', 'reporting_type', 'eligible_for_financial_aid',
            'first_enrollable_paid_seat_price', 'has_ofac_restrictions',
            'enrollment_count', 'recent_enrollment_count',
        )
        read_only_fields = ('enrollment_count', 'recent_enrollment_count',)

    def get_instructors(self, obj):  # pylint: disable=unused-argument
        # This field is deprecated. Use the staff field.
        return []

    def to_internal_value(self, data):
        # Allow incoming writes to just specify a list of slugs for staff
        self.fields['staff'] = serializers.SlugRelatedField(slug_field='uuid', required=False, many=True,
                                                            queryset=Person.objects.all())
        rv = super().to_internal_value(data)
        self.fields['staff'] = MinimalPersonSerializer(required=False, many=True)
        return rv

    def update_video(self, instance, video_data):
        # A separate video object is a historical concept. These days, we really just use the link address. So
        # we look up a foreign key just based on the link and don't bother trying to match or set any other fields.
        # This matches the behavior of our traditional built-in publisher tool. Similarly, we don't try to delete
        # old video entries (just like the publisher tool didn't).
        video_url = video_data and video_data.get('src')
        if video_url:
            video, _ = Video.objects.get_or_create(src=video_url)
            instance.video = video
        else:
            instance.video = None
        # save() will be called by main update()

    def update(self, instance, validated_data):
        # Handle writing nested video data separately
        if 'get_video' in validated_data:
            self.update_video(instance, validated_data.pop('get_video'))

        # Write all other attributes to the instance
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance

    def validate(self, data):
        course = data.get('course', None)
        if course and self.instance and self.instance.course != course:
            raise serializers.ValidationError({'course': _('Course cannot be changed for an existing course run')})

        min_effort = data.get('min_effort', self.instance.min_effort if self.instance else None)
        max_effort = data.get('max_effort', self.instance.max_effort if self.instance else None)
        if min_effort and max_effort and min_effort > max_effort:
            raise serializers.ValidationError({'min_effort': _('Minimum effort cannot be greater than Maximum effort')})
        if min_effort and max_effort and min_effort == max_effort:
            raise serializers.ValidationError({'min_effort': _('Minimum effort and Maximum effort cannot be the same')})
        if not max_effort and min_effort:
            raise serializers.ValidationError({'max_effort': _('Maximum effort cannot be empty')})

        return super().validate(data)


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

            # If flag is not set, remove programs from list that are retired
            if not self.context.get('include_retired_programs'):
                programs = [program for program in programs if program.status != ProgramStatus.Retired]

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


class MinimalCourseSerializer(DynamicFieldsMixin, TimestampModelSerializer):
    course_runs = MinimalCourseRunSerializer(many=True)
    entitlements = CourseEntitlementSerializer(required=False, many=True)
    owners = MinimalOrganizationSerializer(many=True, source='authoring_organizations')
    image = ImageField(read_only=True, source='image_url')
    uuid = UUIDField(read_only=True, default=CreateOnlyDefault(uuid4))

    @classmethod
    def prefetch_queryset(cls, queryset=None, course_runs=None):
        # Explicitly check for None to avoid returning all Courses when the
        # queryset passed in happens to be empty.
        queryset = queryset if queryset is not None else Course.objects.all()

        return queryset.select_related('partner').prefetch_related(
            'authoring_organizations',
            Prefetch('entitlements', queryset=CourseEntitlementSerializer.prefetch_queryset()),
            Prefetch('course_runs', queryset=MinimalCourseRunSerializer.prefetch_queryset(queryset=course_runs)),
        )

    class Meta:
        model = Course
        fields = ('key', 'uuid', 'title', 'course_runs', 'entitlements', 'owners', 'image', 'short_description',)


class CourseSerializer(TaggitSerializer, MinimalCourseSerializer):
    """Serializer for the ``Course`` model."""
    level_type = serializers.SlugRelatedField(required=False, slug_field='name', queryset=LevelType.objects.all())
    subjects = SubjectSerializer(required=False, many=True)  # if you change, change to_internal_value too
    prerequisites = PrerequisiteSerializer(required=False, many=True)
    expected_learning_items = serializers.SlugRelatedField(many=True, read_only=True, slug_field='value')
    video = VideoSerializer(required=False)
    owners = OrganizationSerializer(required=False, many=True, source='authoring_organizations')
    sponsors = OrganizationSerializer(required=False, many=True, source='sponsoring_organizations')
    course_runs = CourseRunSerializer(many=True)
    marketing_url = serializers.SerializerMethodField()
    canonical_course_run_key = serializers.SerializerMethodField()
    original_image = ImageField(read_only=True, source='original_image_url')
    extra_description = AdditionalPromoAreaSerializer(required=False)
    topics = TagListSerializerField(required=False)

    @classmethod
    def prefetch_queryset(cls, partner, queryset=None, course_runs=None):
        # Explicitly check for None to avoid returning all Courses when the
        # queryset passed in happens to be empty.
        queryset = queryset if queryset is not None else Course.objects.filter(partner=partner)

        return queryset.select_related(
            'level_type',
            'video',
            'video__image',
            'partner',
            'extra_description'
        ).prefetch_related(
            'expected_learning_items',
            'prerequisites',
            'subjects',
            'topics',
            Prefetch('course_runs', queryset=CourseRunSerializer.prefetch_queryset(queryset=course_runs)),
            Prefetch('authoring_organizations', queryset=OrganizationSerializer.prefetch_queryset(partner)),
            Prefetch('sponsoring_organizations', queryset=OrganizationSerializer.prefetch_queryset(partner)),
        )

    class Meta(MinimalCourseSerializer.Meta):
        model = Course
        fields = MinimalCourseSerializer.Meta.fields + (
            'full_description', 'level_type', 'subjects', 'prerequisites',
            'prerequisites_raw', 'expected_learning_items', 'video', 'sponsors', 'modified', 'marketing_url',
            'syllabus_raw', 'outcome', 'original_image', 'card_image_url', 'canonical_course_run_key',
            'extra_description', 'additional_information', 'faq', 'learner_testimonials',
            'enrollment_count', 'recent_enrollment_count', 'topics', 'partner',
        )
        extra_kwargs = {
            'partner': {'write_only': True}
        }

    def get_marketing_url(self, obj):
        return get_marketing_url_for_user(
            obj.partner,
            self.context['request'].user,
            obj.marketing_url,
            exclude_utm=self.context.get('exclude_utm')
        )

    def get_canonical_course_run_key(self, obj):
        if obj.canonical_course_run:
            return obj.canonical_course_run.key
        return None

    def to_internal_value(self, data):
        # Allow incoming writes to just specify a list of slugs for subjects
        self.fields['subjects'] = serializers.SlugRelatedField(slug_field='slug',
                                                               required=False,
                                                               many=True,
                                                               queryset=Subject.objects.all())
        rv = super().to_internal_value(data)
        self.fields['subjects'] = SubjectSerializer(required=False, many=True)
        return rv

    def create(self, validated_data):
        return Course.objects.create(**validated_data)


class CourseWithProgramsSerializer(CourseSerializer):
    """A ``CourseSerializer`` which includes programs."""
    course_runs = serializers.SerializerMethodField()
    programs = serializers.SerializerMethodField()

    @classmethod
    def prefetch_queryset(cls, partner, queryset=None, course_runs=None):
        """
        Similar to the CourseSerializer's prefetch_queryset, but prefetches a
        filtered CourseRun queryset.
        """
        queryset = queryset if queryset is not None else Course.objects.filter(partner=partner)
        return queryset.select_related('level_type', 'video', 'video__image', 'partner').prefetch_related(
            'expected_learning_items',
            'prerequisites',
            Prefetch('subjects', queryset=SubjectSerializer.prefetch_queryset()),
            Prefetch('course_runs', queryset=CourseRunSerializer.prefetch_queryset(queryset=course_runs)),
            Prefetch('authoring_organizations', queryset=OrganizationSerializer.prefetch_queryset(partner)),
            Prefetch('sponsoring_organizations', queryset=OrganizationSerializer.prefetch_queryset(partner)),
        )

    # Executes as an n+1 query because of dependence on context
    def get_course_runs(self, course):
        return CourseRunSerializer(
            course.course_runs,
            many=True,
            context={
                'request': self.context.get('request'),
                'exclude_utm': self.context.get('exclude_utm'),
            }
        ).data

    # Executes as an n+1 query because of dependence on context
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
    def prefetch_queryset(cls, partner, queryset=None, course_runs=None):
        """
        Similar to the CourseSerializer's prefetch_queryset, but prefetches a
        filtered CourseRun queryset.
        """
        queryset = queryset if queryset is not None else Course.objects.filter(partner=partner)

        return queryset.select_related('level_type', 'video', 'partner').prefetch_related(
            'expected_learning_items',
            'prerequisites',
            'subjects',
            Prefetch('course_runs', queryset=CourseRunSerializer.prefetch_queryset(queryset=course_runs)),
            Prefetch('authoring_organizations', queryset=OrganizationSerializer.prefetch_queryset(partner)),
            Prefetch('sponsoring_organizations', queryset=OrganizationSerializer.prefetch_queryset(partner)),
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


class RankingSerializer(serializers.ModelSerializer):
    """ Ranking model serializer """
    class Meta:
        model = Ranking
        fields = (
            'rank', 'description', 'source',
        )


class DegreeDeadlineSerializer(serializers.ModelSerializer):
    """ DegreeDeadline model serializer """
    class Meta:
        model = DegreeDeadline
        fields = (
            'semester',
            'name',
            'date',
            'time',
        )


class DegreeCostSerializer(serializers.ModelSerializer):
    """ DegreeCost model serializer """
    class Meta:
        model = DegreeCost
        fields = (
            'description',
            'amount',
        )


class CurriculumSerializer(serializers.ModelSerializer):
    """ Curriculum model serializer """
    courses = serializers.SerializerMethodField()
    programs = serializers.SerializerMethodField()

    class Meta:
        model = Curriculum
        fields = ('uuid', 'name', 'marketing_text', 'marketing_text_brief', 'is_active', 'courses', 'programs')

    def get_courses(self, curriculum):

        course_serializer = MinimalProgramCourseSerializer(
            self.prefetched_courses(curriculum),
            many=True,
            context={
                'request': self.context.get('request'),
                'published_course_runs_only': self.context.get('published_course_runs_only'),
                'exclude_utm': self.context.get('exclude_utm'),
                'course_runs': self.prefetched_course_runs(curriculum),
                'use_full_course_serializer': self.context.get('use_full_course_serializer', False),
            }
        )

        return course_serializer.data

    def get_programs(self, curriculum):

        program_serializer = MinimalProgramSerializer(
            self.prefetched_programs(curriculum),
            many=True,
            context={
                'request': self.context.get('request'),
                'published_course_runs_only': self.context.get('published_course_runs_only'),
                'exclude_utm': self.context.get('exclude_utm'),
                'use_full_course_serializer': self.context.get('use_full_course_serializer', False),
            }
        )

        return program_serializer.data

    def prefetch_course_memberships(self, curriculum):
        """
        Prefetch all member courses and related objects for this curriculum
        """
        if not hasattr(self, '_prefetched_memberships'):
            queryset = CurriculumCourseMembership.objects.filter(curriculum=curriculum).prefetch_related(
                'course',
                'course__course_runs',
                'course__course_runs__seats',
                'course__entitlements',
                'course__authoring_organizations',
                'course__partner',
                'course_run_exclusions',
            )
            self._prefetched_memberships = [membership for membership in queryset]  # pylint: disable=attribute-defined-outside-init

    def prefetch_program_memberships(self, curriculum):
        """
        Prefetch all child programs and related objects for this curriculum
        """
        if not hasattr(self, '_prefetched_program_memberships'):
            queryset = CurriculumProgramMembership.objects.filter(curriculum=curriculum).select_related(
                'program__type', 'program__partner'
            ).prefetch_related(
                'program__excluded_course_runs',
                # `type` is serialized by a third-party serializer. Providing this field name allows us to
                # prefetch `applicable_seat_types`, a m2m on `ProgramType`, through `type`, a foreign key to
                # `ProgramType` on `Program`.
                'program__type__applicable_seat_types',
                'program__authoring_organizations',
                'program__degree',
                Prefetch('program__courses', queryset=MinimalProgramCourseSerializer.prefetch_queryset()),
            )
            self._prefetched_program_memberships = [membership for membership in queryset]  # pylint: disable=attribute-defined-outside-init

    def prefetched_programs(self, curriculum):
        self.prefetch_program_memberships(curriculum)
        return [membership.program for membership in self._prefetched_program_memberships]

    def prefetched_courses(self, curriculum):
        self.prefetch_course_memberships(curriculum)
        return [membership.course for membership in self._prefetched_memberships]

    def prefetched_course_runs(self, curriculum):
        self.prefetch_course_memberships(curriculum)
        return [
            course_run for membership in self._prefetched_memberships
            for course_run in membership.course_runs
        ]


class IconTextPairingSerializer(serializers.ModelSerializer):
    class Meta:
        model = IconTextPairing
        fields = ('text', 'icon',)


class DegreeSerializer(serializers.ModelSerializer):
    """ Degree model serializer """
    campus_image = serializers.ImageField()
    title_background_image = serializers.ImageField()
    costs = DegreeCostSerializer(many=True)
    quick_facts = IconTextPairingSerializer(many=True)
    lead_capture_image = StdImageSerializerField()
    deadlines = DegreeDeadlineSerializer(many=True)
    rankings = RankingSerializer(many=True)
    micromasters_background_image = StdImageSerializerField()

    class Meta:
        model = Degree
        fields = (
            'application_requirements', 'apply_url', 'banner_border_color', 'campus_image', 'title_background_image',
            'costs', 'deadlines', 'lead_capture_list_name', 'quick_facts',
            'overall_ranking', 'prerequisite_coursework', 'rankings',
            'lead_capture_image', 'micromasters_url', 'micromasters_long_title', 'micromasters_long_description',
            'micromasters_background_image', 'costs_fine_print', 'deadlines_fine_print', 'hubspot_lead_capture_form_id',
        )


class MinimalProgramSerializer(DynamicFieldsMixin, serializers.ModelSerializer):
    """
    Basic program serializer

    When using the DynamicFieldsMixin to get the courses field on a program,
    you will also need to include the fields you want on the course object
    since the course serializer also uses drf_dynamic_fields.
    Eg: ?fields=courses,course_runs
    """
    authoring_organizations = MinimalOrganizationSerializer(many=True)
    banner_image = StdImageSerializerField()
    courses = serializers.SerializerMethodField()
    type = serializers.SlugRelatedField(slug_field='name', queryset=ProgramType.objects.all())
    degree = DegreeSerializer()
    curricula = CurriculumSerializer(many=True)

    @classmethod
    def prefetch_queryset(cls, partner, queryset=None):
        # Explicitly check if the queryset is None before selecting related
        queryset = queryset if queryset is not None else Program.objects.filter(partner=partner)

        return queryset.select_related('type', 'partner').prefetch_related(
            'excluded_course_runs',
            # `type` is serialized by a third-party serializer. Providing this field name allows us to
            # prefetch `applicable_seat_types`, a m2m on `ProgramType`, through `type`, a foreign key to
            # `ProgramType` on `Program`.
            'type__applicable_seat_types',
            'authoring_organizations',
            'degree',
            Prefetch('courses', queryset=MinimalProgramCourseSerializer.prefetch_queryset()),
        )

    class Meta:
        model = Program
        fields = (
            'uuid', 'title', 'subtitle', 'type', 'status', 'marketing_slug', 'marketing_url', 'banner_image', 'hidden',
            'courses', 'authoring_organizations', 'card_image_url', 'is_program_eligible_for_one_click_purchase',
            'degree', 'curricula'
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
    staff = MinimalPersonSerializer(many=True)
    instructor_ordering = MinimalPersonSerializer(many=True)
    applicable_seat_types = serializers.SerializerMethodField()
    topics = serializers.SerializerMethodField()

    @classmethod
    def prefetch_queryset(cls, partner, queryset=None):
        """
        Prefetch the related objects that will be serialized with a `Program`.

        We use Prefetch objects so that we can prefetch and select all the way down the
        chain of related fields from programs to course runs (i.e., we want control over
        the querysets that we're prefetching).
        """
        queryset = queryset if queryset is not None else Program.objects.filter(partner=partner)

        return queryset.select_related('type', 'video', 'partner').prefetch_related(
            'excluded_course_runs',
            'expected_learning_items',
            'faq',
            'job_outlook_items',
            'instructor_ordering',
            # `type` is serialized by a third-party serializer. Providing this field name allows us to
            # prefetch `applicable_seat_types`, a m2m on `ProgramType`, through `type`, a foreign key to
            # `ProgramType` on `Program`.
            'type__applicable_seat_types',
            # We need the full Course prefetch here to get CourseRun information that methods on the Program
            # model iterate across (e.g. language). These fields aren't prefetched by the minimal Course serializer.
            Prefetch('courses', queryset=CourseSerializer.prefetch_queryset(partner=partner)),
            Prefetch('authoring_organizations', queryset=OrganizationSerializer.prefetch_queryset(partner)),
            Prefetch('credit_backing_organizations', queryset=OrganizationSerializer.prefetch_queryset(partner)),
            Prefetch('corporate_endorsements', queryset=CorporateEndorsementSerializer.prefetch_queryset()),
            Prefetch('individual_endorsements', queryset=EndorsementSerializer.prefetch_queryset()),
        )

    def get_applicable_seat_types(self, obj):
        return list(obj.type.applicable_seat_types.values_list('slug', flat=True))

    def get_topics(self, obj):
        return [topic.name for topic in obj.topics]

    class Meta(MinimalProgramSerializer.Meta):
        model = Program
        fields = MinimalProgramSerializer.Meta.fields + (
            'overview', 'total_hours_of_effort', 'weeks_to_complete', 'weeks_to_complete_min', 'weeks_to_complete_max',
            'min_hours_effort_per_week', 'max_hours_effort_per_week', 'video', 'expected_learning_items',
            'faq', 'credit_backing_organizations', 'corporate_endorsements', 'job_outlook_items',
            'individual_endorsements', 'languages', 'transcript_languages', 'subjects', 'price_ranges',
            'staff', 'credit_redemption_overview', 'applicable_seat_types', 'instructor_ordering',
            'enrollment_count', 'recent_enrollment_count', 'topics',
        )


class PathwaySerializer(serializers.ModelSerializer):
    """ Serializer for Pathway. """
    uuid = serializers.CharField()
    name = serializers.CharField()
    org_name = serializers.CharField()
    email = serializers.EmailField()
    programs = MinimalProgramSerializer(many=True)
    description = serializers.CharField()
    destination_url = serializers.CharField()
    pathway_type = serializers.CharField()

    class Meta:
        model = Pathway
        fields = (
            'id',
            'uuid',
            'name',
            'org_name',
            'email',
            'programs',
            'description',
            'destination_url',
            'pathway_type',
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

    # These field names are dictated by Affiliate Window (AWIN). These fields are
    # required. They're documented at http://wiki.awin.com/index.php/Product_Feed_File_Structure.
    pid = serializers.SerializerMethodField()
    name = serializers.CharField(source='course_run.title')
    desc = serializers.CharField(source='course_run.full_description')
    purl = serializers.CharField(source='course_run.marketing_url')
    imgurl = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()

    # These fields are optional. They're documented at
    # http://wiki.awin.com/index.php/Product_Feed_Advanced_File_Structure.
    lang = serializers.SerializerMethodField()
    validfrom = serializers.DateTimeField(source='course_run.start', format='%Y-%m-%d')
    validto = serializers.DateTimeField(source='course_run.end', format='%Y-%m-%d')
    # These field names are required by AWIN for data that doesn't fit into one
    # of their default fields.
    custom1 = serializers.CharField(source='course_run.pacing_type')
    custom2 = serializers.SlugRelatedField(source='course_run.level_type', read_only=True, slug_field='name')
    custom3 = serializers.SerializerMethodField()
    custom4 = serializers.SerializerMethodField()
    custom5 = serializers.CharField(source='course_run.short_description')

    class Meta:
        model = Seat
        # The order of these fields must match the order in which they appear in
        # the DTD file! Validation will fail otherwise.
        fields = (
            'name',
            'pid',
            'desc',
            'category',
            'purl',
            'imgurl',
            'price',
            'lang',
            'currency',
            'validfrom',
            'validto',
            'custom1',
            'custom2',
            'custom3',
            'custom4',
            'custom5',
        )

    def get_pid(self, obj):
        return '{}-{}'.format(obj.course_run.key, obj.type)

    def get_price(self, obj):
        return {
            'actualp': obj.price
        }

    def get_category(self, obj):  # pylint: disable=unused-argument
        return self.CATEGORY

    def get_lang(self, obj):
        language = obj.course_run.language

        return language.code.split('-')[0].upper() if language else 'EN'

    def get_custom3(self, obj):
        return ','.join(subject.name for subject in obj.course_run.subjects.all())

    def get_custom4(self, obj):
        return ','.join(org.name for org in obj.course_run.authoring_organizations.all())

    def get_imgurl(self, obj):
        return obj.course_run.card_image_url or obj.course_run.course.card_image_url


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
            'masters': {
                'type': ''
            }
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
    serialize_objects = True

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
    course_runs = serializers.SerializerMethodField()

    def get_course_runs(self, result):
        return [
            {
                'key': course_run.key,
                'enrollment_start': course_run.enrollment_start,
                'enrollment_end': course_run.enrollment_end,
                'start': course_run.start,
                'end': course_run.end,
            }
            for course_run in result.object.course_runs.all()
        ]

    class Meta:
        field_aliases = COMMON_SEARCH_FIELD_ALIASES
        ignore_fields = COMMON_IGNORED_FIELDS
        index_classes = [search_indexes.CourseIndex]
        fields = search_indexes.BASE_SEARCH_INDEX_FIELDS + (
            'full_description',
            'key',
            'short_description',
            'title',
            'card_image_url',
            'course_runs',
            'uuid',
            'subjects',
            'languages',
        )


class CourseFacetSerializer(BaseHaystackFacetSerializer):
    class Meta:
        field_aliases = COMMON_SEARCH_FIELD_ALIASES
        ignore_fields = COMMON_IGNORED_FIELDS
        field_options = {
            'level_type': {},
            'organizations': {},
            'prerequisites': {},
            'subjects': {},
        }


class CourseRunSearchSerializer(HaystackSerializer):
    availability = serializers.SerializerMethodField()
    first_enrollable_paid_seat_price = serializers.SerializerMethodField()

    def get_availability(self, result):
        return result.object.availability

    def get_first_enrollable_paid_seat_price(self, result):
        return result.object.first_enrollable_paid_seat_price

    class Meta:
        field_aliases = COMMON_SEARCH_FIELD_ALIASES
        ignore_fields = COMMON_IGNORED_FIELDS
        index_classes = [search_indexes.CourseRunIndex]
        fields = search_indexes.BASE_SEARCH_INDEX_FIELDS + (
            'authoring_organization_uuids',
            'availability',
            'end',
            'enrollment_end',
            'enrollment_start',
            'first_enrollable_paid_seat_sku',
            'first_enrollable_paid_seat_price',
            'full_description',
            'has_enrollable_seats',
            'image_url',
            'key',
            'language',
            'level_type',
            'logo_image_urls',
            'marketing_url',
            'max_effort',
            'min_effort',
            'mobile_available',
            'number',
            'org',
            'pacing_type',
            'partner',
            'program_types',
            'published',
            'seat_types',
            'short_description',
            'staff_uuids',
            'start',
            'subject_uuids',
            'text',
            'title',
            'transcript_languages',
            'type',
            'weeks_to_complete'
        )


class CourseRunFacetSerializer(BaseHaystackFacetSerializer):
    class Meta:
        field_aliases = COMMON_SEARCH_FIELD_ALIASES
        ignore_fields = COMMON_IGNORED_FIELDS
        field_options = {
            'content_type': {},
            'language': {},
            'level_type': {},
            'mobile_available': {},
            'organizations': {'size': settings.SEARCH_FACET_LIMIT},
            'pacing_type': {},
            'first_enrollable_paid_seat_price': {},
            'prerequisites': {},
            'seat_types': {},
            'subjects': {},
            'transcript_languages': {},
            'type': {},
        }
        field_queries = {
            'availability_current': {'query': 'start:<now AND end:>now'},
            'availability_starting_soon': {'query': 'start:[now TO now+60d]'},
            'availability_upcoming': {'query': 'start:[now+60d TO *]'},
            'availability_archived': {'query': 'end:<=now'},
        }


class PersonSearchSerializer(HaystackSerializer):
    profile_image_url = serializers.SerializerMethodField()

    def get_profile_image_url(self, result):
        return result.object.get_profile_image_url

    class Meta:
        field_aliases = COMMON_SEARCH_FIELD_ALIASES
        ignore_fields = COMMON_IGNORED_FIELDS
        index_classes = [search_indexes.PersonIndex]
        fields = search_indexes.BASE_SEARCH_INDEX_FIELDS + (
            'uuid',
            'salutation',
            'full_name',
            'bio',
            'bio_language',
            'profile_image_url',
            'position',
            'organizations',
        )


class PersonSearchModelSerializer(HaystackSerializerMixin, ContentTypeSerializer, MinimalPersonSerializer):
    class Meta(MinimalPersonSerializer.Meta):
        fields = ContentTypeSerializer.Meta.fields + MinimalPersonSerializer.Meta.fields


class PersonFacetSerializer(BaseHaystackFacetSerializer):
    class Meta:
        field_aliases = COMMON_SEARCH_FIELD_ALIASES
        ignore_fields = COMMON_IGNORED_FIELDS
        index_classes = [search_indexes.PersonIndex]
        fields = ('organizations',)
        field_options = {
            'organizations': {},
        }


class ProgramSearchSerializer(HaystackSerializer):
    authoring_organizations = serializers.SerializerMethodField()

    def get_authoring_organizations(self, program):
        organizations = program.authoring_organization_bodies
        return [json.loads(organization) for organization in organizations] if organizations else []

    class Meta:
        field_aliases = COMMON_SEARCH_FIELD_ALIASES
        ignore_fields = COMMON_IGNORED_FIELDS
        index_classes = [search_indexes.ProgramIndex]
        fields = search_indexes.BASE_SEARCH_INDEX_FIELDS + search_indexes.BASE_PROGRAM_FIELDS + (
            'authoring_organization_uuids',
            'authoring_organizations',
            'hidden',
            'is_program_eligible_for_one_click_purchase',
            'max_hours_effort_per_week',
            'min_hours_effort_per_week',
            'staff_uuids',
            'subject_uuids',
            'weeks_to_complete_max',
            'weeks_to_complete_min',
            'search_card_display'
        )


class ProgramFacetSerializer(BaseHaystackFacetSerializer):
    class Meta:
        field_aliases = COMMON_SEARCH_FIELD_ALIASES
        ignore_fields = COMMON_IGNORED_FIELDS
        index_classes = [search_indexes.ProgramIndex]
        field_options = {
            'status': {},
            'type': {},
            'seat_types': {},
        }
        fields = search_indexes.BASE_PROGRAM_FIELDS + (
            'organizations',
        )


class AggregateSearchSerializer(HaystackSerializer):
    class Meta:
        field_aliases = COMMON_SEARCH_FIELD_ALIASES
        ignore_fields = COMMON_IGNORED_FIELDS
        fields = CourseRunSearchSerializer.Meta.fields + ProgramSearchSerializer.Meta.fields + \
            CourseSearchSerializer.Meta.fields
        serializers = {
            search_indexes.CourseRunIndex: CourseRunSearchSerializer,
            search_indexes.CourseIndex: CourseSearchSerializer,
            search_indexes.ProgramIndex: ProgramSearchSerializer,
            search_indexes.PersonIndex: PersonSearchSerializer,
        }


class AggregateFacetSearchSerializer(BaseHaystackFacetSerializer):
    class Meta:
        field_aliases = COMMON_SEARCH_FIELD_ALIASES
        ignore_fields = COMMON_IGNORED_FIELDS
        field_queries = CourseRunFacetSerializer.Meta.field_queries
        field_options = {
            **CourseRunFacetSerializer.Meta.field_options,
            **ProgramFacetSerializer.Meta.field_options
        }
        serializers = {
            search_indexes.CourseRunIndex: CourseRunFacetSerializer,
            search_indexes.CourseIndex: CourseFacetSerializer,
            search_indexes.ProgramIndex: ProgramFacetSerializer,
            search_indexes.PersonIndex: PersonFacetSerializer,
        }


class CourseSearchModelSerializer(HaystackSerializerMixin, ContentTypeSerializer, CourseWithProgramsSerializer):
    class Meta(CourseWithProgramsSerializer.Meta):
        fields = ContentTypeSerializer.Meta.fields + CourseWithProgramsSerializer.Meta.fields


class CourseRunSearchModelSerializer(HaystackSerializerMixin, ContentTypeSerializer, CourseRunWithProgramsSerializer):
    class Meta(CourseRunWithProgramsSerializer.Meta):
        fields = ContentTypeSerializer.Meta.fields + CourseRunWithProgramsSerializer.Meta.fields


class ProgramSearchModelSerializer(HaystackSerializerMixin, ContentTypeSerializer, ProgramSerializer):
    class Meta(ProgramSerializer.Meta):
        fields = ContentTypeSerializer.Meta.fields + ProgramSerializer.Meta.fields


class AggregateSearchModelSerializer(HaystackSerializer):
    class Meta:
        serializers = {
            search_indexes.CourseRunIndex: CourseRunSearchModelSerializer,
            search_indexes.CourseIndex: CourseSearchModelSerializer,
            search_indexes.ProgramIndex: ProgramSearchModelSerializer,
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


class TopicSerializer(serializers.ModelSerializer):
    """Serializer for the ``Topic`` model."""

    @classmethod
    def prefetch_queryset(cls):
        return Topic.objects.filter()

    class Meta(object):
        model = Topic
        fields = ('name', 'subtitle', 'description', 'long_description', 'banner_image_url', 'slug', 'uuid')
