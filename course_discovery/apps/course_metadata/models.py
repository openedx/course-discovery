import datetime
import itertools
import logging
from collections import Counter, defaultdict
from operator import attrgetter
from urllib.parse import urljoin
from uuid import uuid4

import pytz
import waffle
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models, transaction
from django.db.models import F, Q
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from django_extensions.db.fields import AutoSlugField
from django_extensions.db.models import TimeStampedModel
from haystack.query import SearchQuerySet
from parler.models import TranslatableModel, TranslatedFieldsModel
from simple_history.models import HistoricalRecords
from solo.models import SingletonModel
from sortedm2m.fields import SortedManyToManyField
from stdimage.models import StdImageField
from stdimage.utils import UploadToAutoSlug
from taggit_autosuggest.managers import TaggableManager

from course_discovery.apps.core.models import Currency, Partner
from course_discovery.apps.course_metadata import emails
from course_discovery.apps.course_metadata.choices import (
    CertificateType, CourseRunPacing, CourseRunStatus, PayeeType, ProgramStatus, ReportingType
)
from course_discovery.apps.course_metadata.constants import PathwayType
from course_discovery.apps.course_metadata.fields import HtmlField, NullHtmlField
from course_discovery.apps.course_metadata.managers import DraftManager
from course_discovery.apps.course_metadata.people import MarketingSitePeople
from course_discovery.apps.course_metadata.publishers import (
    CourseRunMarketingSitePublisher, ProgramMarketingSitePublisher
)
from course_discovery.apps.course_metadata.query import CourseQuerySet, CourseRunQuerySet, ProgramQuerySet
from course_discovery.apps.course_metadata.utils import (
    UploadToFieldNamePath, clean_query, custom_render_variations, push_to_ecommerce_for_course_run, set_official_state,
    uslugify
)
from course_discovery.apps.ietf_language_tags.models import LanguageTag
from course_discovery.apps.publisher.utils import VALID_CHARS_IN_COURSE_NUM_AND_ORG_KEY

logger = logging.getLogger(__name__)


class DraftModelMixin(models.Model):
    """
    Defines a draft boolean field and an object manager to make supporting drafts more transparent.

    This defines two managers. The 'everything' manager will return all rows. The 'objects' manager will exclude
    draft versions by default unless you also define the 'objects' manager.

    Remember to add 'draft' to your unique_together clauses.

    Django doesn't allow real model mixins, but since everything has to inherit from models.Model, we shouldn't be
    stepping on anyone's toes. This is the best advice I could find (at time of writing for Django 1.11).

    .. no_pii:
    """
    draft = models.BooleanField(default=False, help_text='Is this a draft version?')
    draft_version = models.OneToOneField('self', models.SET_NULL, null=True, blank=True,
                                         related_name='_official_version', limit_choices_to={'draft': True})

    everything = models.Manager()
    objects = DraftManager()

    @property
    def official_version(self):
        """
        Related name fields will return an exception when there is no connection.  In that case we want to return None
        Returns:
            None: if there is no Official Version
        """
        try:
            return self._official_version
        except ObjectDoesNotExist:
            return None

    class Meta:
        abstract = True


class CachedMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cache = dict(self.__dict__)

    def refresh_from_db(self, using=None, fields=None, **kwargs):
        super().refresh_from_db(using, fields, **kwargs)
        self.__dict__.pop('_cache', None)
        self._cache = dict(self.__dict__)

    def save(self, **kwargs):
        super().save(**kwargs)
        self.__dict__.pop('_cache', None)
        self._cache = dict(self.__dict__)

    def did_change(self, field):
        return field in self.__dict__ and (field not in self._cache or getattr(self, field) != self._cache[field])


class AbstractNamedModel(TimeStampedModel):
    """ Abstract base class for models with only a name field. """
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        abstract = True


class AbstractValueModel(TimeStampedModel):
    """ Abstract base class for models with only a value field. """
    value = models.CharField(max_length=255)

    def __str__(self):
        return self.value

    class Meta:
        abstract = True


class AbstractMediaModel(TimeStampedModel):
    """ Abstract base class for media-related (e.g. image, video) models. """
    src = models.URLField(max_length=255, unique=True)
    description = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.src

    class Meta:
        abstract = True


class AbstractTitleDescriptionModel(TimeStampedModel):
    """ Abstract base class for models with a title and description pair. """
    title = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        if self.title:
            return self.title
        return self.description

    class Meta:
        abstract = True


class Image(AbstractMediaModel):
    """ Image model. """
    height = models.IntegerField(null=True, blank=True)
    width = models.IntegerField(null=True, blank=True)


class Video(AbstractMediaModel):
    """ Video model. """
    image = models.ForeignKey(Image, models.CASCADE, null=True, blank=True)

    def __str__(self):
        return '{src}: {description}'.format(src=self.src, description=self.description)


class LevelType(AbstractNamedModel):
    """ LevelType model. """
    order = models.PositiveSmallIntegerField(default=0, db_index=True)

    class Meta:
        ordering = ('order',)


class SeatType(TimeStampedModel):
    name = models.CharField(max_length=64)
    slug = AutoSlugField(populate_from='name', slugify_function=uslugify, unique=True)

    def __str__(self):
        return self.name


class ProgramType(TimeStampedModel):
    XSERIES = 'xseries'
    MICROMASTERS = 'micromasters'
    PROFESSIONAL_CERTIFICATE = 'professional-certificate'
    PROFESSIONAL_PROGRAM_WL = 'professional-program-wl'
    MASTERS = 'masters'

    name = models.CharField(max_length=32, unique=True, null=False, blank=False)
    applicable_seat_types = models.ManyToManyField(
        SeatType, help_text=_('Seat types that qualify for completion of programs of this type. Learners completing '
                              'associated courses, but enrolled in other seat types, will NOT have their completion '
                              'of the course counted toward the completion of the program.'),
    )
    logo_image = StdImageField(
        upload_to=UploadToAutoSlug(populate_from='name', path='media/program_types/logo_images'),
        blank=True,
        null=True,
        variations={
            'large': (256, 256),
            'medium': (128, 128),
            'small': (64, 64),
            'x-small': (32, 32),
        },
        help_text=_('Please provide an image file with transparent background'),
    )
    slug = AutoSlugField(populate_from='name', editable=True, unique=True, slugify_function=uslugify,
                         help_text=_('Leave this field blank to have the value generated automatically.'))

    # Do not record the slug field in the history table because AutoSlugField is not compatible with
    # django-simple-history.  Background: https://github.com/edx/course-discovery/pull/332
    history = HistoricalRecords(excluded_fields=['slug'])

    def __str__(self):
        return self.name

    @staticmethod
    def get_program_type_data(pub_course_run, program_model):
        slug = None
        name = None
        program_type = None

        if pub_course_run.is_micromasters:
            slug = ProgramType.MICROMASTERS
            name = pub_course_run.micromasters_name
        elif pub_course_run.is_professional_certificate:
            slug = ProgramType.PROFESSIONAL_CERTIFICATE
            name = pub_course_run.professional_certificate_name
        elif pub_course_run.is_xseries:
            slug = ProgramType.XSERIES
            name = pub_course_run.xseries_name
        if slug:
            program_type = program_model.objects.get(slug=slug)
        return program_type, name


class Mode(TimeStampedModel):
    """
    This model is similar to the LMS CourseMode model.

    It holds several fields that (one day will) control logic for handling enrollments in this mode.
    Examples of names would be "Verified", "Credit", or "Masters"

    See docs/decisions/0009-LMS-types-in-course-metadata.rst for more information.
    """
    name = models.CharField(max_length=64)
    slug = models.CharField(max_length=64, unique=True)
    is_id_verified = models.BooleanField(default=False, help_text=_('This mode requires ID verification.'))
    is_credit_eligible = models.BooleanField(
        default=False,
        help_text=_('Completion can grant credit toward an organization’s degree.'),
    )
    certificate_type = models.CharField(
        max_length=64, choices=CertificateType, blank=True,
        help_text=_('Certificate type granted if this mode is eligible for a certificate, or blank if not.'),
    )
    payee = models.CharField(
        max_length=64, choices=PayeeType, default='', blank=True,
        help_text=_('Who gets paid for the course? Platform is the site owner, Organization is the school.'),
    )

    history = HistoricalRecords()

    def __str__(self):
        return self.name

    @property
    def is_certificate_eligible(self):
        """
        Returns True if completion can impart any kind of certificate to the learner.
        """
        return bool(self.certificate_type)


class Track(TimeStampedModel):
    """
    This model ties a Mode (an LMS concept) with a SeatType (an E-Commerce concept)

    Basically, a track is all the metadata for a single enrollment type, with both the course logic and product sides.

    See docs/decisions/0009-LMS-types-in-course-metadata.rst for more information.
    """
    seat_type = models.ForeignKey(SeatType, models.CASCADE, null=True, blank=True)
    mode = models.ForeignKey(Mode, models.CASCADE)

    history = HistoricalRecords()

    def __str__(self):
        return self.mode.name


class CourseRunType(TimeStampedModel):
    """
    This model defines the enrollment options (Tracks) for a given course run.

    A single course might have runs with different enrollment options. Like a course that has a
    "Masters, Verified, and Audit" CourseType might contain CourseRunTypes named
    - "Masters, Verified, and Audit" (pointing to three different tracks)
    - "Verified and Audit"
    - "Audit only"
    - "Masters only"

    See docs/decisions/0009-LMS-types-in-course-metadata.rst for more information.
    """
    AUDIT = 'audit'
    VERIFIED_AUDIT = 'verified-audit'
    PROFESSIONAL = 'professional'
    CREDIT_VERIFIED_AUDIT = 'credit-verified-audit'

    uuid = models.UUIDField(default=uuid4, editable=False, verbose_name=_('UUID'), unique=True)
    name = models.CharField(max_length=64)
    slug = models.CharField(max_length=64, unique=True)
    tracks = models.ManyToManyField(Track)
    is_marketable = models.BooleanField(default=True)

    history = HistoricalRecords()

    def __str__(self):
        return self.name


class CourseType(TimeStampedModel):
    """
    This model defines the permissible types of enrollments provided by a whole course.

    It holds a list of permissible entitlement options and a list of permissible CourseRunTypes.

    Examples of names would be "Masters, Verified, and Audit" or "Verified and Audit"
    """
    AUDIT = 'audit'
    VERIFIED_AUDIT = 'verified-audit'
    PROFESSIONAL = 'professional'
    CREDIT_VERIFIED_AUDIT = 'credit-verified-audit'

    uuid = models.UUIDField(default=uuid4, editable=False, verbose_name=_('UUID'), unique=True)
    name = models.CharField(max_length=64)
    slug = models.CharField(max_length=64, unique=True)
    entitlement_types = models.ManyToManyField(SeatType, blank=True)
    course_run_types = SortedManyToManyField(
        CourseRunType, help_text=_('Sets the order for displaying Course Run Types.')
    )

    history = HistoricalRecords()

    def __str__(self):
        return self.name


class Subject(TranslatableModel, TimeStampedModel):
    """ Subject model. """
    uuid = models.UUIDField(blank=False, null=False, default=uuid4, editable=False, verbose_name=_('UUID'))
    banner_image_url = models.URLField(blank=True, null=True)
    card_image_url = models.URLField(blank=True, null=True)
    slug = AutoSlugField(populate_from='name', editable=True, blank=True, slugify_function=uslugify,
                         help_text=_('Leave this field blank to have the value generated automatically.'))

    partner = models.ForeignKey(Partner, models.CASCADE)

    def __str__(self):
        return self.name

    class Meta:
        unique_together = (
            ('partner', 'slug'),
            ('partner', 'uuid'),
        )
        ordering = ['created']

    def validate_unique(self, *args, **kwargs):  # pylint: disable=arguments-differ
        super(Subject, self).validate_unique(*args, **kwargs)
        qs = Subject.objects.filter(partner=self.partner_id)
        if qs.filter(translations__name=self.name).exclude(pk=self.pk).exists():
            raise ValidationError({'name': ['Subject with this Name and Partner already exists', ]})


class SubjectTranslation(TranslatedFieldsModel):  # pylint: disable=model-no-explicit-unicode
    master = models.ForeignKey(Subject, models.CASCADE, related_name='translations', null=True)

    name = models.CharField(max_length=255, blank=False, null=False)
    subtitle = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ('language_code', 'master')
        verbose_name = _('Subject model translations')


class Topic(TranslatableModel, TimeStampedModel):
    """ Topic model. """
    uuid = models.UUIDField(blank=False, null=False, default=uuid4, editable=False, verbose_name=_('UUID'))
    banner_image_url = models.URLField(blank=True, null=True)
    slug = AutoSlugField(populate_from='name', editable=True, blank=True, slugify_function=uslugify,
                         help_text=_('Leave this field blank to have the value generated automatically.'))

    partner = models.ForeignKey(Partner, models.CASCADE)

    def __str__(self):
        return self.name

    class Meta:
        unique_together = (
            ('partner', 'slug'),
            ('partner', 'uuid'),
        )
        ordering = ['created']

    def validate_unique(self, *args, **kwargs):  # pylint: disable=arguments-differ
        super(Topic, self).validate_unique(*args, **kwargs)
        qs = Topic.objects.filter(partner=self.partner_id)
        if qs.filter(translations__name=self.name).exclude(pk=self.pk).exists():
            raise ValidationError({'name': ['Topic with this Name and Partner already exists', ]})


class TopicTranslation(TranslatedFieldsModel):  # pylint: disable=model-no-explicit-unicode
    master = models.ForeignKey(Topic, models.CASCADE, related_name='translations', null=True)

    name = models.CharField(max_length=255, blank=False, null=False)
    subtitle = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    long_description = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ('language_code', 'master')
        verbose_name = _('Topic model translations')


class Prerequisite(AbstractNamedModel):
    """ Prerequisite model. """


class ExpectedLearningItem(AbstractValueModel):
    """ ExpectedLearningItem model. """


class JobOutlookItem(AbstractValueModel):
    """ JobOutlookItem model. """


class SyllabusItem(AbstractValueModel):
    """ SyllabusItem model. """
    parent = models.ForeignKey('self', models.CASCADE, blank=True, null=True, related_name='children')


class AdditionalPromoArea(AbstractTitleDescriptionModel):
    """ Additional Promo Area Model """


class Organization(CachedMixin, TimeStampedModel):
    """ Organization model. """
    partner = models.ForeignKey(Partner, models.CASCADE, null=True, blank=False)
    uuid = models.UUIDField(blank=False, null=False, default=uuid4, editable=False, verbose_name=_('UUID'))
    key = models.CharField(max_length=255, help_text=_('Please do not use any spaces or special characters other '
                                                       'than period, underscore or hyphen. This key will be used '
                                                       'in the course\'s course key.'))
    name = models.CharField(max_length=255)
    slug = AutoSlugField(populate_from='key', editable=False, slugify_function=uslugify)
    description = models.TextField(null=True, blank=True)
    homepage_url = models.URLField(max_length=255, null=True, blank=True)
    logo_image_url = models.URLField(null=True, blank=True)
    banner_image_url = models.URLField(null=True, blank=True)
    certificate_logo_image_url = models.URLField(
        null=True, blank=True, help_text=_('Logo to be displayed on certificates. If this logo is the same as '
                                           'logo_image_url, copy and paste the same value to both fields.')
    )
    salesforce_id = models.CharField(max_length=255, null=True, blank=True)  # Publisher_Organization__c in Salesforce

    tags = TaggableManager(
        blank=True,
        help_text=_('Pick a tag from the suggestions. To make a new tag, add a comma after the tag name.'),
    )

    def clean(self):
        if not VALID_CHARS_IN_COURSE_NUM_AND_ORG_KEY.match(self.key):
            raise ValidationError(_('Please do not use any spaces or special characters other than period, '
                                    'underscore or hyphen in the key field.'))

    class Meta:
        unique_together = (
            ('partner', 'key'),
            ('partner', 'uuid'),
        )
        ordering = ['created']

    def __str__(self):
        if self.name and self.name != self.key:
            return '{key}: {name}'.format(key=self.key, name=self.name)
        else:
            return self.key

    @property
    def marketing_url(self):
        if self.slug and self.partner:
            return urljoin(self.partner.marketing_site_url_root, 'school/' + self.slug)

        return None

    @classmethod
    def user_organizations(cls, user):
        return cls.objects.filter(organization_extension__group__in=user.groups.all())


class Person(TimeStampedModel):
    """ Person model. """
    uuid = models.UUIDField(blank=False, null=False, default=uuid4, editable=False, verbose_name=_('UUID'))
    partner = models.ForeignKey(Partner, models.CASCADE, null=True, blank=False)
    salutation = models.CharField(max_length=10, null=True, blank=True)
    given_name = models.CharField(max_length=255)
    family_name = models.CharField(max_length=255, null=True, blank=True)
    bio = NullHtmlField()
    bio_language = models.ForeignKey(LanguageTag, models.CASCADE, null=True, blank=True)
    profile_image = StdImageField(
        upload_to=UploadToFieldNamePath(populate_from='uuid', path='media/people/profile_images'),
        blank=True,
        null=True,
        variations={
            'medium': (110, 110),
        },
    )
    slug = AutoSlugField(populate_from=('given_name', 'family_name'), editable=True, slugify_function=uslugify)
    email = models.EmailField(null=True, blank=True, max_length=255)
    major_works = HtmlField(
        blank=True,
        help_text=_('A list of major works by this person. Must be valid HTML.'),
    )
    published = models.BooleanField(default=False)

    class Meta:
        unique_together = (
            ('partner', 'uuid'),
        )
        verbose_name_plural = _('People')
        ordering = ['created']

    def __str__(self):
        return self.full_name

    def save(self, *args, **kwargs):  # pylint: disable=arguments-differ
        with transaction.atomic():
            super(Person, self).save(*args, **kwargs)
            if waffle.switch_is_active('publish_person_to_marketing_site'):
                MarketingSitePeople().update_or_publish_person(self)

        logger.info('Person saved UUID: %s', self.uuid, exc_info=True)

    @property
    def full_name(self):
        if self.family_name:
            full_name = ' '.join((self.given_name, self.family_name,))
            if self.salutation:
                return ' '.join((self.salutation, full_name,))

            return full_name
        else:
            return self.given_name

    @property
    def profile_url(self):
        return self.partner.marketing_site_url_root + 'bio/' + self.slug

    @property
    def get_profile_image_url(self):
        if self.profile_image and hasattr(self.profile_image, 'url'):
            return self.profile_image.url
        return None


class Position(TimeStampedModel):
    """ Position model.

    This model represent's a `Person`'s role at an organization.
    """
    person = models.OneToOneField(Person, models.CASCADE)
    title = models.CharField(max_length=255)
    organization = models.ForeignKey(Organization, models.CASCADE, null=True, blank=True)
    organization_override = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return '{title} at {organization}'.format(title=self.title, organization=self.organization_name)

    @property
    def organization_name(self):
        name = self.organization_override

        if self.organization and not name:
            name = self.organization.name

        return name


class PkSearchableMixin:
    """
    Represents objects that have a search method to query elasticsearch and load by primary key.
    """

    @classmethod
    def search(cls, query, queryset=None):
        """ Queries the search index.

        Args:
            query (str) -- Elasticsearch querystring (e.g. `title:intro*`)
            queryset (models.QuerySet) -- base queryset to search, defaults to objects.all()

        Returns:
            QuerySet
        """
        query = clean_query(query)

        if queryset is None:
            queryset = cls.objects.all()

        if query == '(*)':
            # Early-exit optimization. Wildcard searching is very expensive in elasticsearch. And since we just
            # want everything, we don't need to actually query elasticsearch at all.
            return queryset

        results = SearchQuerySet().models(cls).raw_search(query)
        ids = {result.pk for result in results}

        return queryset.filter(pk__in=ids)


class Course(DraftModelMixin, PkSearchableMixin, CachedMixin, TimeStampedModel):
    """ Course model. """
    partner = models.ForeignKey(Partner, models.CASCADE)
    uuid = models.UUIDField(default=uuid4, editable=False, verbose_name=_('UUID'))
    canonical_course_run = models.OneToOneField(
        'course_metadata.CourseRun', models.CASCADE, related_name='canonical_for_course',
        default=None, null=True, blank=True,
    )
    key = models.CharField(max_length=255, db_index=True)
    key_for_reruns = models.CharField(
        max_length=255, blank=True,
        help_text=_('When making reruns for this course, they will use this key instead of the course key.'),
    )
    title = models.CharField(max_length=255, default=None, null=True, blank=True)
    url_slug = AutoSlugField(populate_from='title', editable=True, slugify_function=uslugify, overwrite_on_add=False,
                             help_text=_('Leave this field blank to have the value generated automatically.'))
    short_description = NullHtmlField()
    full_description = NullHtmlField()
    extra_description = models.ForeignKey(
        AdditionalPromoArea, models.CASCADE, default=None, null=True, blank=True, related_name='extra_description',
    )
    authoring_organizations = SortedManyToManyField(Organization, blank=True, related_name='authored_courses')
    sponsoring_organizations = SortedManyToManyField(Organization, blank=True, related_name='sponsored_courses')
    subjects = SortedManyToManyField(Subject, blank=True)
    prerequisites = models.ManyToManyField(Prerequisite, blank=True)
    level_type = models.ForeignKey(LevelType, models.CASCADE, default=None, null=True, blank=True)
    expected_learning_items = SortedManyToManyField(ExpectedLearningItem, blank=True)
    outcome = NullHtmlField()
    prerequisites_raw = NullHtmlField()
    syllabus_raw = NullHtmlField()
    card_image_url = models.URLField(null=True, blank=True)
    image = StdImageField(
        upload_to=UploadToFieldNamePath(populate_from='uuid', path='media/course/image'),
        blank=True,
        null=True,
        variations={
            'original': (1134, 675),
            'small': (378, 225)
        },
        help_text=_('Add the course image')
    )
    slug = AutoSlugField(populate_from='key', editable=True, slugify_function=uslugify)
    video = models.ForeignKey(Video, models.CASCADE, default=None, null=True, blank=True)
    faq = NullHtmlField(verbose_name=_('FAQ'))
    learner_testimonials = NullHtmlField()
    enrollment_count = models.IntegerField(
        null=True, blank=True, default=0, help_text=_('Total number of learners who have enrolled in this course')
    )
    recent_enrollment_count = models.IntegerField(
        null=True, blank=True, default=0, help_text=_(
            'Total number of learners who have enrolled in this course in the last 6 months'
        )
    )
    salesforce_id = models.CharField(max_length=255, null=True, blank=True)  # Course__c in Salesforce
    salesforce_case_id = models.CharField(max_length=255, null=True, blank=True)  # Case in Salesforce
    type = models.ForeignKey(CourseType, models.CASCADE, null=True, blank=True)

    # Do not record the slug field in the history table because AutoSlugField is not compatible with
    # django-simple-history.  Background: https://github.com/edx/course-discovery/pull/332
    history = HistoricalRecords(excluded_fields=['slug', 'url_slug'])

    # TODO Remove this field.
    number = models.CharField(
        max_length=50, null=True, blank=True, help_text=_(
            'Course number format e.g CS002x, BIO1.1x, BIO1.2x'
        )
    )

    topics = TaggableManager(
        blank=True,
        help_text=_('Pick a tag from the suggestions. To make a new tag, add a comma after the tag name.'),
        related_name='course_topics',
    )

    # The 'additional_information' field holds HTML content, but we don't use a NullHtmlField for it, because we don't
    # want to validate its content at all. This is filled in by administrators, not course teams, and may hold special
    # HTML that isn't normally allowed.
    additional_information = models.TextField(blank=True, null=True, default=None,
                                              verbose_name=_('Additional Information'))

    everything = CourseQuerySet.as_manager()
    objects = DraftManager.from_queryset(CourseQuerySet)()

    class Meta:
        unique_together = (
            ('partner', 'uuid', 'draft'),
            ('partner', 'key', 'draft'),
        )
        ordering = ['id']

    def __str__(self):
        return '{key}: {title}'.format(key=self.key, title=self.title)

    def clean(self):
        # We need to populate the value with 0 - model blank and null definitions are to validate the admin form.
        if self.enrollment_count is None:
            self.enrollment_count = 0
        if self.recent_enrollment_count is None:
            self.recent_enrollment_count = 0

    @property
    def image_url(self):
        if self.image:
            return self.image.small.url

        return self.card_image_url

    @property
    def original_image_url(self):
        if self.image:
            return self.image.url
        return None

    @property
    def marketing_url(self):
        url = None
        if self.partner.marketing_site_url_root:
            path = 'course/{slug}'.format(slug=self.slug)
            url = urljoin(self.partner.marketing_site_url_root, path)

        return url

    @property
    def active_url_slug(self):
        """ Official rows just return whatever slug is active, draft rows will first look for an associated active
         slug and, if they fail to find one, take the slug associated with the official course that has
         is_active_on_draft: True."""
        if not self.draft:
            return self.url_slug_history.get(is_active=True).url_slug
        else:
            try:
                return self.url_slug_history.get(is_active=True).url_slug
            except ObjectDoesNotExist:
                # current draft url slug has already been published at least once, so get it from the official course
                if self.official_version:
                    return self.official_version.url_slug_history.get(is_active_on_draft=True).url_slug
                return None

    def course_run_sort(self, course_run):
        """
        Sort course runs by enrollment_start or start, preferring the former

        A missing date is stubbed to max datetime to be sorted last
        """
        date = course_run.enrollment_start or course_run.start
        if date:
            return date
        return datetime.datetime.max.replace(tzinfo=pytz.UTC)

    @property
    def active_course_runs(self):
        """ Returns course runs that have not yet ended and meet the following enrollment criteria:
            - Open for enrollment
            - OR will be open for enrollment in the future
            - OR have no specified enrollment close date (e.g. self-paced courses)

        This is basically a QuerySet version of "all runs where has_enrollment_ended is False"

        Returns:
            QuerySet
        """
        now = datetime.datetime.now(pytz.UTC)
        return self.course_runs.filter(
            Q(end__gt=now) &
            (
                Q(enrollment_end__gt=now) |
                Q(enrollment_end__isnull=True)
            )
        )

    @property
    def first_enrollable_paid_seat_price(self):
        """
        Sort the course runs with sorted rather than order_by to avoid
        additional calls to the database
        """
        for course_run in sorted(
            self.active_course_runs,
            key=lambda active_course_run: active_course_run.key.lower(),
        ):
            if course_run.has_enrollable_paid_seats():
                return course_run.first_enrollable_paid_seat_price

        return None

    @property
    def course_run_statuses(self):
        statuses = self.course_runs.filter(hidden=False).values_list('status', flat=True).distinct().order_by('status')
        return list(statuses)

    def update_marketing_redirects(self, published_runs=None):
        """
        Find old course runs that are no longer active but still published.
        These will be unpublished and linked to an active course run.

        Designed to work on official runs.

        Arguments:
            published_runs (iterable): optional optimization; pass published CourseRuns to avoid a lookup

        Returns:
            True if any redirects were changed
        """
        if not self.partner.has_marketing_site:
            return False

        if published_runs is None:
            published_runs = self.course_runs.filter(status=CourseRunStatus.Published).iterator()
        published_runs = frozenset(published_runs)

        # Now separate out the active ones from the inactive
        # (done in Python rather than hitting self.active_course_runs to avoid a second db query)
        now = datetime.datetime.now(pytz.UTC)
        inactive_runs = {run for run in published_runs if run.has_enrollment_ended(now)}
        active_runs = published_runs - inactive_runs
        if not active_runs or not inactive_runs:
            return False  # if there are no runs to redirect from or to, there's no point in continuing

        # Find the earliest active run, to which we will redirect any inactive runs
        earliest_active_run = min(active_runs, key=attrgetter('start'))

        publisher = CourseRunMarketingSitePublisher(self.partner)
        for run in inactive_runs:
            publisher.add_url_redirect(earliest_active_run, run)
            run.status = CourseRunStatus.Unpublished
            run.save()
            if run.draft_version:
                run.draft_version.status = CourseRunStatus.Unpublished
                run.draft_version.save()

        return True

    def _update_or_create_official_version(self, course_run):
        """
        Should only be called from CourseRun.update_or_create_official_version. Because we only need to make draft
        changes official in the context of a course run and because certain actions (like publishing data to ecommerce)
        happen when we make official versions and we want to do those as a bundle with the course run.
        """
        draft_version = Course.everything.get(pk=self.pk)
        # If there isn't an official_version set yet, then this is a create instead of update
        # and we will want to set additional attributes.
        creating = not self.official_version

        official_version = set_official_state(draft_version, Course)

        for entitlement in self.entitlements.all():
            # The draft version could have audit entitlements, but we only
            # want to create official entitlements for the valid entitlement modes.
            if entitlement.mode.slug in Seat.ENTITLEMENT_MODES:
                set_official_state(entitlement, CourseEntitlement, {'course': official_version})

        official_version.set_active_url_slug(self.active_url_slug)

        if creating:
            official_version.canonical_course_run = course_run
            official_version.slug = self.slug
            official_version.save()
            self.canonical_course_run = course_run.draft_version
            self.save()

        return official_version

    @transaction.atomic
    def set_active_url_slug(self, slug):
        if self.draft:
            active_draft_url_slug_object = self.url_slug_history.filter(is_active=True).first()

            # case 1: new slug matches an entry in the course's slug history
            if self.official_version:
                found = False
                for url_entry in self.official_version.url_slug_history.filter(Q(is_active_on_draft=True) |
                                                                               Q(url_slug=slug)):
                    match = url_entry.url_slug == slug
                    url_entry.is_active_on_draft = match
                    found = found or match
                    url_entry.save()
                if found:
                    # we will get the active slug via the official object, so delete the draft one
                    if active_draft_url_slug_object:
                        active_draft_url_slug_object.delete()
                    return
            # case 2: slug has not been used for this course before
            obj = self.url_slug_history.update_or_create(is_active=True, defaults={  # pylint: disable=no-member
                'course': self,
                'partner': self.partner,
                'is_active': True,
                'url_slug': slug,
            })[0]  # update_or_create returns an (obj, created?) tuple, so just get the object
            # this line necessary to clear the prefetch cache
            self.url_slug_history.add(obj)  # pylint: disable=no-member
        else:
            if self.draft_version:
                self.draft_version.url_slug_history.filter(is_active=True).delete()
            obj = self.url_slug_history.update_or_create(url_slug=slug, defaults={  # pylint: disable=no-member
                'url_slug': slug,
                'is_active': True,
                'is_active_on_draft': True,
                'partner': self.partner,
            })[0]
            for other_slug in self.url_slug_history.filter(Q(is_active=True) |
                                                           Q(is_active_on_draft=True)).exclude(url_slug=obj.url_slug):
                other_slug.is_active = False
                other_slug.is_active_on_draft = False
                other_slug.save()


class CourseEditor(TimeStampedModel):
    """
    CourseEditor model, defining who can edit a course and its course runs.

    .. no_pii:
    """
    user = models.ForeignKey(get_user_model(), models.CASCADE, related_name='courses_edited')
    course = models.ForeignKey(Course, models.CASCADE, related_name='editors')

    class Meta:
        unique_together = ('user', 'course',)

    # The logic for whether a user can edit a course gets a little complicated, so try to use the following class
    # utility methods when possible. Read 0003-publisher-permission.rst for more context on the why.

    @classmethod
    def can_create_course(cls, user, organization_key):
        if user.is_staff:
            return True

        # You must be a member of the organization within which you are creating a course
        return user.groups.filter(organization_extension__organization__key=organization_key).exists()

    @classmethod
    def course_editors(cls, course):
        """
        Returns an iterable of User objects.
        """
        authoring_orgs = course.authoring_organizations.all()

        # No matter what, if an editor or their organization has been removed from the course, they can't be an editor
        # for it. This handles cases of being dropped from an org... But might be too restrictive in case we want
        # to allow outside guest editors on a course? Let's try this for now and see how it goes.
        valid_editors = course.editors.filter(user__groups__organization_extension__organization__in=authoring_orgs)
        valid_editors = valid_editors.select_related('user')

        if valid_editors:
            return {editor.user for editor in valid_editors}

        # No valid editors - this is an edge case where we just grant anyone in an authoring org access
        user_model = get_user_model()
        return user_model.objects.filter(groups__organization_extension__organization__in=authoring_orgs).distinct()

    @classmethod
    def editors_for_user(cls, user):
        if user.is_staff:
            return CourseEditor.objects.all()

        user_orgs = Organization.user_organizations(user)
        return CourseEditor.objects.filter(user__groups__organization_extension__organization__in=user_orgs)

    @classmethod
    def is_course_editable(cls, user, course):
        if user.is_staff:
            return True

        return user in cls.course_editors(course)

    @classmethod
    def editable_courses(cls, user, queryset, check_editors=True):
        if user.is_staff:
            return queryset

        # We must be a valid editor for this course
        if check_editors:
            has_valid_editors = Q(
                editors__user__groups__organization_extension__organization__in=F('authoring_organizations')
            )
            has_user_editor = Q(editors__user=user)
            queryset = queryset.filter(has_user_editor | ~has_valid_editors)

        # And the course has to be authored by an org we belong to
        user_orgs = Organization.user_organizations(user)
        queryset = queryset.filter(authoring_organizations__in=user_orgs)

        # We use distinct() here because the query is complicated enough, spanning tables and following lists of
        # foreign keys, that django will return duplicate rows if we aren't careful to ask it not to.
        return queryset.distinct()

    @classmethod
    def editable_course_runs(cls, user, queryset):
        if user.is_staff:
            return queryset

        user_orgs = Organization.user_organizations(user)
        has_valid_editors = Q(
            course__editors__user__groups__organization_extension__organization__in=F('course__authoring_organizations')
        )
        has_user_editor = Q(course__editors__user=user)
        user_can_edit = has_user_editor | ~has_valid_editors

        # We use distinct() here because the query is complicated enough, spanning tables and following lists of
        # foreign keys, that django will return duplicate rows if we aren't careful to ask it not to.
        return queryset.filter(user_can_edit, course__authoring_organizations__in=user_orgs).distinct()


class CourseRun(DraftModelMixin, CachedMixin, TimeStampedModel):
    """ CourseRun model. """
    OFAC_RESTRICTION_CHOICES = (
        ('', '--'),
        (True, _('Restricted')),
        (False, _('Not restricted')),
    )

    uuid = models.UUIDField(default=uuid4, verbose_name=_('UUID'))
    course = models.ForeignKey(Course, models.CASCADE, related_name='course_runs')
    key = models.CharField(max_length=255)
    # There is a post save function in signals.py that verifies that this is unique within a program
    external_key = models.CharField(max_length=225, blank=True, null=True)
    status = models.CharField(default=CourseRunStatus.Unpublished, max_length=255, null=False, blank=False,
                              db_index=True, choices=CourseRunStatus.choices, validators=[CourseRunStatus.validator])
    title_override = models.CharField(
        max_length=255, default=None, null=True, blank=True,
        help_text=_(
            "Title specific for this run of a course. Leave this value blank to default to the parent course's title."))
    start = models.DateTimeField(null=True, blank=True, db_index=True)
    end = models.DateTimeField(null=True, blank=True, db_index=True)
    go_live_date = models.DateTimeField(null=True, blank=True)
    enrollment_start = models.DateTimeField(null=True, blank=True)
    enrollment_end = models.DateTimeField(null=True, blank=True, db_index=True)
    announcement = models.DateTimeField(null=True, blank=True)
    short_description_override = NullHtmlField(
        help_text=_(
            "Short description specific for this run of a course. Leave this value blank to default to "
            "the parent course's short_description attribute."))
    full_description_override = NullHtmlField(
        help_text=_(
            "Full description specific for this run of a course. Leave this value blank to default to "
            "the parent course's full_description attribute."))
    staff = SortedManyToManyField(Person, blank=True, related_name='courses_staffed')
    min_effort = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text=_('Estimated minimum number of hours per week needed to complete a course run.'))
    max_effort = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text=_('Estimated maximum number of hours per week needed to complete a course run.'))
    weeks_to_complete = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text=_('Estimated number of weeks needed to complete this course run.'))
    language = models.ForeignKey(LanguageTag, models.CASCADE, null=True, blank=True)
    transcript_languages = models.ManyToManyField(LanguageTag, blank=True, related_name='transcript_courses')
    pacing_type = models.CharField(max_length=255, db_index=True, null=True, blank=True,
                                   choices=CourseRunPacing.choices, validators=[CourseRunPacing.validator])
    syllabus = models.ForeignKey(SyllabusItem, models.CASCADE, default=None, null=True, blank=True)
    enrollment_count = models.IntegerField(
        null=True, blank=True, default=0, help_text=_('Total number of learners who have enrolled in this course run')
    )
    recent_enrollment_count = models.IntegerField(
        null=True, blank=True, default=0, help_text=_(
            'Total number of learners who have enrolled in this course run in the last 6 months'
        )
    )

    # TODO Ditch this, and fallback to the course
    card_image_url = models.URLField(null=True, blank=True)
    video = models.ForeignKey(Video, models.CASCADE, default=None, null=True, blank=True)
    video_translation_languages = models.ManyToManyField(
        LanguageTag, blank=True, related_name='+')
    slug = AutoSlugField(max_length=255, populate_from='title', slugify_function=uslugify, db_index=True,
                         editable=True)
    hidden = models.BooleanField(default=False)
    mobile_available = models.BooleanField(default=False)
    course_overridden = models.BooleanField(
        default=False,
        help_text=_('Indicates whether the course relation has been manually overridden.')
    )
    reporting_type = models.CharField(max_length=255, choices=ReportingType.choices, default=ReportingType.mooc)
    eligible_for_financial_aid = models.BooleanField(default=True)
    license = models.CharField(max_length=255, blank=True, db_index=True)
    outcome_override = NullHtmlField(
        help_text=_(
            "'What You Will Learn' description for this particular course run. Leave this value blank to default "
            "to the parent course's Outcome attribute."))
    type = models.ForeignKey(CourseRunType, models.CASCADE, null=True, blank=True)

    tags = TaggableManager(
        blank=True,
        help_text=_('Pick a tag from the suggestions. To make a new tag, add a comma after the tag name.'),
    )

    has_ofac_restrictions = models.NullBooleanField(
        blank=True,
        choices=OFAC_RESTRICTION_CHOICES,
        default=None,
        verbose_name=_('Add OFAC restriction text to the FAQ section of the Marketing site'),
    )
    ofac_comment = models.TextField(blank=True, help_text='Comment related to OFAC restriction')

    # The expected_program_type and expected_program_name are here in support of Publisher and may not reflect the
    # final program information.
    expected_program_type = models.ForeignKey(ProgramType, models.CASCADE, default=None, null=True, blank=True)
    expected_program_name = models.CharField(max_length=255, default='', blank=True)

    everything = CourseRunQuerySet.as_manager()
    objects = DraftManager.from_queryset(CourseRunQuerySet)()

    # Do not record the slug field in the history table because AutoSlugField is not compatible with
    # django-simple-history.  Background: https://github.com/edx/course-discovery/pull/332
    history = HistoricalRecords(excluded_fields=['slug'])

    salesforce_id = models.CharField(max_length=255, null=True, blank=True)  # Course_Run__c in Salesforce

    STATUS_CHANGE_EXEMPT_FIELDS = [
        'start',
        'end',
        'go_live_date',
        'staff',
        'min_effort',
        'max_effort',
        'weeks_to_complete',
        'language',
        'transcript_languages',
        'pacing_type',
    ]

    INTERNAL_REVIEW_FIELDS = (
        'status',
        'has_ofac_restrictions',
        'ofac_comment',
    )

    class Meta:
        unique_together = (
            ('key', 'draft'),
            ('uuid', 'draft'),
        )

    def __init__(self, *args, **kwargs):
        super(CourseRun, self).__init__(*args, **kwargs)
        self._old_status = self.status

    def _upgrade_deadline_sort(self, seat):
        """
        Stub missing upgrade_deadlines to max datetime so they are ordered last
        """
        if seat and seat.upgrade_deadline:
            return seat.upgrade_deadline
        return datetime.datetime.max.replace(tzinfo=pytz.UTC)

    def _enrollable_paid_seats(self):
        """
        Return a list that may be used to fetch the enrollable paid Seats (Seats with price > 0 and no
        prerequisites) associated with this CourseRun.

        We don't use django's built in filter() here since the API should have prefetched seats and
        filter() would hit the database again
        """
        seats = []
        for seat in self.seats.all():
            if seat.type.slug not in Seat.SEATS_WITH_PREREQUISITES and seat.price > 0.0:
                seats.append(seat)
        return seats

    def clean(self):
        # See https://stackoverflow.com/questions/47819247
        if self.enrollment_count is None:
            self.enrollment_count = 0
        if self.recent_enrollment_count is None:
            self.recent_enrollment_count = 0

    @property
    def first_enrollable_paid_seat_price(self):
        # Sort in python to avoid an additional request to the database for order_by
        seats = sorted(self._enrollable_paid_seats(), key=self._upgrade_deadline_sort)
        if not seats:
            # Enrollable paid seats are not available for this CourseRun.
            return None

        price = int(seats[0].price) if seats[0].price else None
        return price

    def first_enrollable_paid_seat_sku(self):
        # Sort in python to avoid an additional request to the database for order_by
        seats = sorted(self._enrollable_paid_seats(), key=self._upgrade_deadline_sort)
        if not seats:
            # Enrollable paid seats are not available for this CourseRun.
            return None
        first_enrollable_paid_seat_sku = seats[0].sku
        return first_enrollable_paid_seat_sku

    def has_enrollable_paid_seats(self):
        """
        Return a boolean indicating whether or not enrollable paid Seats (Seats with price > 0 and no prerequisites)
        are available for this CourseRun.
        """
        return len(self._enrollable_paid_seats()[:1]) > 0

    def is_current_and_still_upgradeable(self):
        """
        Return true if
        1. Today is after the run start (or start is none) and two weeks from the run end (or end is none)
        2. The run has a seat that is still enrollable and upgradeable
        and false otherwise
        """
        now = datetime.datetime.now(pytz.UTC)
        two_weeks = datetime.timedelta(days=14)
        after_start = (not self.start) or (self.start and self.start < now)
        ends_in_more_than_two_weeks = (not self.end) or (self.end.date() and now.date() <= self.end.date() - two_weeks)
        if after_start and ends_in_more_than_two_weeks:
            paid_seat_enrollment_end = self.get_paid_seat_enrollment_end()
            if paid_seat_enrollment_end and now < paid_seat_enrollment_end:
                return True
        return False

    def get_paid_seat_enrollment_end(self):
        """
        Return the final date for which an unenrolled user may enroll and purchase a paid Seat for this CourseRun, or
        None if the date is unknown or enrollable paid Seats are not available.
        """
        # Sort in python to avoid an additional request to the database for order_by
        seats = sorted(
            self._enrollable_paid_seats(),
            key=self._upgrade_deadline_sort,
            reverse=True,
        )
        if not seats:
            # Enrollable paid seats are not available for this CourseRun.
            return None

        # An unenrolled user may not enroll and purchase paid seats after the course or enrollment has ended.
        deadline = self.enrollment_deadline

        seat = seats[0]
        if seat.upgrade_deadline and (deadline is None or seat.upgrade_deadline < deadline):
            deadline = seat.upgrade_deadline

        return deadline

    def enrollable_seats(self, types=None):
        """
        Returns seats, of the given type(s), that can be enrolled in/purchased.

        Arguments:
            types (list of SeatTypes): Type of seats to limit the returned value to.

        Returns:
            List of Seats
        """
        now = datetime.datetime.now(pytz.UTC)

        enrolls_in_future = self.enrollment_start and self.enrollment_start > now
        if self.has_enrollment_ended(now) or enrolls_in_future:
            return []

        enrollable_seats = []
        types = types or SeatType.objects.all()
        for seat in self.seats.all():
            if seat.type in types and (not seat.upgrade_deadline or now < seat.upgrade_deadline):
                enrollable_seats.append(seat)

        return enrollable_seats

    @property
    def has_enrollable_seats(self):
        """
        Return a boolean indicating whether or not enrollable Seats are available for this CourseRun.
        """
        return len(self.enrollable_seats()) > 0

    @property
    def image_url(self):
        return self.course.image_url

    @property
    def program_types(self):
        """
        Exclude unpublished and deleted programs from list
        so we don't identify that program type if not available
        """
        program_statuses_to_exclude = (ProgramStatus.Unpublished, ProgramStatus.Deleted)
        associated_programs = []
        for program in self.programs.exclude(status__in=program_statuses_to_exclude):
            if self not in program.excluded_course_runs.all():
                associated_programs.append(program)
        return [program.type.name for program in associated_programs]

    @property
    def marketing_url(self):
        if self.slug:
            path = 'course/{slug}'.format(slug=self.slug)
            return urljoin(self.course.partner.marketing_site_url_root, path)

        return None

    @property
    def title(self):
        return self.title_override or self.course.title

    @title.setter
    def title(self, value):
        # Treat empty strings as NULL
        value = value or None
        self.title_override = value

    @property
    def short_description(self):
        return self.short_description_override or self.course.short_description

    @short_description.setter
    def short_description(self, value):
        # Treat empty strings as NULL
        value = value or None
        self.short_description_override = value

    @property
    def full_description(self):
        return self.full_description_override or self.course.full_description

    @full_description.setter
    def full_description(self, value):
        # Treat empty strings as NULL
        value = value or None
        self.full_description_override = value

    @property
    def outcome(self):
        return self.outcome_override or self.course.outcome

    @property
    def in_review(self):
        return self.status in CourseRunStatus.REVIEW_STATES()

    @outcome.setter
    def outcome(self, value):
        # Treat empty strings as NULL
        value = value or None
        self.outcome_override = value

    @property
    def subjects(self):
        return self.course.subjects

    @property
    def authoring_organizations(self):
        return self.course.authoring_organizations

    @property
    def sponsoring_organizations(self):
        return self.course.sponsoring_organizations

    @property
    def prerequisites(self):
        return self.course.prerequisites

    @property
    def programs(self):
        return self.course.programs  # pylint: disable=no-member

    @property
    def seat_types(self):
        return [seat.type for seat in self.seats.all()]

    @property
    def type_legacy(self):
        """
        Calculates a single type slug from the seats in this run.

        This is a property that makes less sense these days. It used to be called simply `type`. But now that Tracks
        and Modes and CourseRunType have made our mode / type situation less rigid, this is losing relevance.

        For example, this cannot support modes that don't have corresponding seats (like Masters).

        It's better to just look at all the modes in the run via type -> tracks -> modes and base any logic off that
        rather than trying to read the tea leaves at the entire run level. The mode combinations are just too complex
        these days.
        """
        seat_types = {t.slug for t in self.seat_types}
        mapping = (
            ('credit', {'credit'}),
            ('professional', {'professional', 'no-id-professional'}),
            ('verified', {'verified'}),
            ('honor', {'honor'}),
            ('audit', {'audit'}),
        )

        for course_run_type, matching_seat_types in mapping:
            if matching_seat_types & seat_types:
                return course_run_type

        return None

    @property
    def level_type(self):
        return self.course.level_type

    @property
    def availability(self):
        now = datetime.datetime.now(pytz.UTC)
        upcoming_cutoff = now + datetime.timedelta(days=60)

        if self.has_ended(now):
            return _('Archived')
        elif self.start and (self.start <= now):
            return _('Current')
        elif self.start and (now < self.start < upcoming_cutoff):
            return _('Starting Soon')
        else:
            return _('Upcoming')

    @property
    def get_video(self):
        return self.video or self.course.video

    @classmethod
    def search(cls, query):
        """ Queries the search index.
        Args:
            query (str) -- Elasticsearch querystring (e.g. `title:intro*`)
        Returns:
            SearchQuerySet
        """
        query = clean_query(query)
        queryset = SearchQuerySet().models(cls)

        if query == '(*)':
            # Early-exit optimization. Wildcard searching is very expensive in elasticsearch. And since we just
            # want everything, we don't need to actually query elasticsearch at all.
            return queryset.load_all()

        return queryset.raw_search(query).load_all()

    def __str__(self):
        return '{key}: {title}'.format(key=self.key, title=self.title)

    def validate_seat_upgrade(self, seat_types):
        """
        If a course run has an official version, then ecom products have already been created and
        we only support changing mode from audit -> verified
        """
        if self.official_version:
            old_types = set(self.official_version.seats.values_list('type', flat=True))  # returns strings
            new_types = {t.slug for t in seat_types}
            if new_types & set(Seat.REQUIRES_AUDIT_SEAT):
                new_types.add(Seat.AUDIT)
            if old_types - new_types:
                raise ValidationError(_('Switching seat types after being reviewed is not supported. Please reach out '
                                        'to your project coordinator for additional help if necessary.'))

    def get_seat_upgrade_deadline(self, seat_type):
        deadline = None
        # only verified seats have a deadline specified
        if seat_type.slug == Seat.VERIFIED:
            seats = self.seats.filter(type=seat_type)
            if seats:
                deadline = seats[0].upgrade_deadline
            else:
                deadline = self.end - datetime.timedelta(days=settings.PUBLISHER_UPGRADE_DEADLINE_DAYS)
                deadline = deadline.replace(hour=23, minute=59, second=59, microsecond=99999)
        return deadline

    def update_or_create_seat_helper(self, seat_type, prices):
        defaults = {
            'upgrade_deadline': self.get_seat_upgrade_deadline(seat_type),
        }
        if seat_type.slug in prices:
            defaults['price'] = prices[seat_type.slug]

        Seat.everything.update_or_create(
            course_run=self,
            type=seat_type,
            draft=True,
            defaults=defaults,
        )

    def update_or_create_seats(self, run_type=None, prices=None):
        """
        Updates or creates draft seats for a course run.

        Supports being able to switch seat types to any type before an official version of the
        course run exists. After an official version of the course run exists, it only supports
        price changes or upgrades from Audit -> Verified.
        """
        ignore_types = set()  # an extra list of seat types to ignore / keep around
        prices = dict(prices or {})

        # DISCO-1399: Shouldn't need the whole if/else anymore. Can also look into if it's necessary
        # to keep all of the helper functions (helper, validate, and upgrade deadline)
        if run_type:
            seat_types = {track.seat_type for track in run_type.tracks.exclude(seat_type=None)}
        else:
            course_entitlement = self.course.entitlements.first()  # pylint: disable=no-member
            seat_types = set()
            if course_entitlement:
                seat_types.add(course_entitlement.mode)
            if not course_entitlement or course_entitlement.mode.slug in Seat.REQUIRES_AUDIT_SEAT:
                seat_types.add(SeatType.objects.get(slug=Seat.AUDIT))

            # Publisher does not yet handle credit/honor seats. But we don't want to delete them or change their price.
            # So just save them from deletion but don't update. They'll be handled better in new CourseType flow.
            ignore_types.update(SeatType.objects.filter(slug__in=[Seat.CREDIT, Seat.HONOR]))

        allowed_types = seat_types | ignore_types
        self.validate_seat_upgrade(allowed_types)

        for seat_type in seat_types:
            self.update_or_create_seat_helper(seat_type, prices)

        # Deleting seats here since they would be orphaned otherwise.
        # One example of how this situation can happen is if a course team is switching between
        # professional and verified before actually publishing their course run.
        self.seats.exclude(type__in=allowed_types).delete()

    def update_or_create_official_version(self, create_ecom_products=True):
        draft_version = CourseRun.everything.get(pk=self.pk)
        official_version = set_official_state(draft_version, CourseRun)

        for seat in self.seats.all():
            set_official_state(seat, Seat, {'course_run': official_version})

        official_course = self.course._update_or_create_official_version(official_version)  # pylint: disable=protected-access
        official_version.slug = self.slug
        official_version.course = official_course

        official_version.save()

        # Push any product (seat, entitlement) changes to ecommerce as well
        if create_ecom_products:
            push_to_ecommerce_for_course_run(official_version)
        return official_version

    def handle_status_change(self, send_emails):
        """
        If a row's status changed, take any cleanup actions necessary.

        Mostly this is sending email notifications to interested parties or converting a draft row to an official
        one.
        """
        if self._old_status == self.status:
            return
        self._old_status = self.status

        # We currently only care about draft course runs
        if not self.draft:
            return

        # OK, now check for various status change triggers

        email_method = None

        if self.status == CourseRunStatus.LegalReview:
            email_method = emails.send_email_for_legal_review

        elif self.status == CourseRunStatus.InternalReview:
            email_method = emails.send_email_for_internal_review

        elif self.status == CourseRunStatus.Reviewed:
            official_version = self.update_or_create_official_version()

            # If we're due to go live already and we just now got reviewed, immediately go live
            if self.go_live_date and self.go_live_date <= datetime.datetime.now(pytz.UTC):
                official_version.publish()  # will edit/save us too
            else:  # The publish status check will send an email for go-live
                email_method = emails.send_email_for_reviewed

        elif self.status == CourseRunStatus.Published:
            email_method = emails.send_email_for_go_live

        if send_emails and email_method:
            email_method(self)

    def save(self, suppress_publication=False, send_emails=True, **kwargs):  # pylint: disable=arguments-differ
        """
        Arguments:
            suppress_publication (bool): if True, we won't push the run data to the marketing site
            send_emails (bool): whether to send email notifications for status changes from this save
        """
        is_new_course_run = not self.id
        push_to_marketing = (not suppress_publication and
                             self.course.partner.has_marketing_site and
                             waffle.switch_is_active('publish_course_runs_to_marketing_site') and
                             not self.draft)

        with transaction.atomic():
            if push_to_marketing:
                previous_obj = CourseRun.objects.get(id=self.id) if self.id else None

            super().save(**kwargs)
            self.handle_status_change(send_emails)

            if push_to_marketing:
                self.push_to_marketing_site(previous_obj)

        if is_new_course_run:
            retired_programs = self.programs.filter(status=ProgramStatus.Retired)
            for program in retired_programs:
                program.excluded_course_runs.add(self)

    def publish(self, send_emails=True):
        """
        Marks the course run as announced and published if it is time to do so.

        Course run must be an official version - both it and any draft version will be published.
        Marketing site redirects will also be updated.

        Args:
            send_emails (bool): whether to send email notifications for this publish action

        Returns:
            True if the run was published, False if it was not eligible
        """
        if self.draft:
            return False

        now = datetime.datetime.now(pytz.UTC)
        with transaction.atomic():
            for run in filter(None, [self, self.draft_version]):
                run.announcement = now
                run.status = CourseRunStatus.Published
                run.save(send_emails=send_emails)

        # It is likely that we are sunsetting an old run in favor of this new run, so update redirects just in case
        self.course.update_marketing_redirects()

        return True

    def push_to_marketing_site(self, previous_obj):
        publisher = CourseRunMarketingSitePublisher(self.course.partner)
        publisher.publish_obj(self, previous_obj=previous_obj)

    def has_ended(self, when=None):
        """
        Returns:
            True if course run has a defined end and it has passed
        """
        when = when or datetime.datetime.now(pytz.UTC)
        return bool(self.end and self.end < when)

    def has_enrollment_ended(self, when=None):
        """
        Returns:
            True if the enrollment deadline is defined and has passed
        """
        when = when or datetime.datetime.now(pytz.UTC)
        deadline = self.enrollment_deadline
        return bool(deadline and deadline < when)

    @property
    def enrollment_deadline(self):
        """
        Returns:
            The datetime past which this run cannot be enrolled in (or ideally, marketed) or None if no restriction
        """
        dates = set(filter(None, [self.end, self.enrollment_end]))
        return min(dates) if dates else None

    @property
    def is_enrollable(self):
        """
        Checks if the course run is currently enrollable

        Note that missing enrollment_end or enrollment_start are considered to
        mean that the course run does not have a restriction on the respective
        fields.
        Additionally, we don't consider the end date because archived course
        runs may have ended, but they are always enrollable since they have
        null enrollment_start and enrollment_end.
        """
        now = datetime.datetime.now(pytz.UTC)
        return ((not self.enrollment_end or self.enrollment_end >= now) and
                (not self.enrollment_start or self.enrollment_start <= now))

    @property
    def is_marketable(self):
        """
        Checks if the course_run is currently marketable

        A course run is considered marketable if it's published, has seats, and
        a non-empty marketing url.
        """
        is_published = self.status == CourseRunStatus.Published

        return is_published and self.seats.exists() and bool(self.marketing_url)


class Seat(DraftModelMixin, TimeStampedModel):
    """ Seat model. """

    # This set of class variables is historic. Before CourseType and Mode and all that jazz, Seat used to just hold
    # a CharField 'type' and the logic around what that meant often used these variables. We can slowly remove
    # these hardcoded variables as code stops referencing them and using dynamic Modes.
    HONOR = 'honor'
    AUDIT = 'audit'
    VERIFIED = 'verified'
    PROFESSIONAL = 'professional'
    CREDIT = 'credit'
    MASTERS = 'masters'
    ENTITLEMENT_MODES = [VERIFIED, PROFESSIONAL]
    REQUIRES_AUDIT_SEAT = [VERIFIED]
    # Seat types that we don't push to ecommerce -- they are either manually or never created as products
    NON_PRODUCT_MODES = [CREDIT, MASTERS]
    # Seat types that may not be purchased without first purchasing another Seat type.
    # EX: 'credit' seats may not be purchased without first purchasing a 'verified' Seat.
    SEATS_WITH_PREREQUISITES = [CREDIT]

    PRICE_FIELD_CONFIG = {
        'decimal_places': 2,
        'max_digits': 10,
        'null': False,
        'default': 0.00,
    }
    course_run = models.ForeignKey(CourseRun, models.CASCADE, related_name='seats')
    # The 'type' field used to be a CharField but when we converted to a ForeignKey, we kept the db column the same,
    # by specifying a bunch of these extra kwargs.
    type = models.ForeignKey(SeatType, models.CASCADE,
                             to_field='slug',  # this keeps the columns as a string, not an int
                             db_column='type')  # this avoids renaming the column to type_id
    price = models.DecimalField(**PRICE_FIELD_CONFIG)
    currency = models.ForeignKey(Currency, models.CASCADE, default='USD')
    upgrade_deadline = models.DateTimeField(null=True, blank=True)
    credit_provider = models.CharField(max_length=255, null=True, blank=True)
    credit_hours = models.IntegerField(null=True, blank=True)
    sku = models.CharField(max_length=128, null=True, blank=True)
    bulk_sku = models.CharField(max_length=128, null=True, blank=True)

    history = HistoricalRecords()

    class Meta:
        unique_together = (
            ('course_run', 'type', 'currency', 'credit_provider', 'draft')
        )
        ordering = ['created']


class CourseEntitlement(DraftModelMixin, TimeStampedModel):
    """ Model storing product metadata for a Course. """
    PRICE_FIELD_CONFIG = {
        'decimal_places': 2,
        'max_digits': 10,
        'null': False,
        'default': 0.00,
    }
    course = models.ForeignKey(Course, models.CASCADE, related_name='entitlements')
    mode = models.ForeignKey(SeatType, models.CASCADE)
    partner = models.ForeignKey(Partner, models.CASCADE, null=True, blank=False)
    price = models.DecimalField(**PRICE_FIELD_CONFIG)
    currency = models.ForeignKey(Currency, models.CASCADE, default='USD')
    sku = models.CharField(max_length=128, null=True, blank=True)

    history = HistoricalRecords()

    class Meta:
        unique_together = (
            ('course', 'draft')
        )
        ordering = ['created']


class Endorsement(TimeStampedModel):
    endorser = models.ForeignKey(Person, models.CASCADE, blank=False, null=False)
    quote = models.TextField(blank=False, null=False)

    def __str__(self):
        return self.endorser.full_name


class CorporateEndorsement(TimeStampedModel):
    corporation_name = models.CharField(max_length=128, blank=False, null=False)
    statement = models.TextField(null=True, blank=True)
    image = models.ForeignKey(Image, models.CASCADE, blank=True, null=True)
    individual_endorsements = SortedManyToManyField(Endorsement)

    def __str__(self):
        return self.corporation_name


class FAQ(TimeStampedModel):
    question = models.TextField(blank=False, null=False)
    answer = models.TextField(blank=False, null=False)

    class Meta:
        verbose_name = _('FAQ')
        verbose_name_plural = _('FAQs')
        ordering = ['created']

    def __str__(self):
        return self.question


class Program(PkSearchableMixin, TimeStampedModel):
    uuid = models.UUIDField(blank=True, default=uuid4, editable=False, unique=True, verbose_name=_('UUID'))
    title = models.CharField(
        help_text=_('The user-facing display title for this Program.'), max_length=255, unique=True)
    subtitle = models.CharField(
        help_text=_('A brief, descriptive subtitle for the Program.'), max_length=255, blank=True)
    type = models.ForeignKey(ProgramType, models.CASCADE, null=True, blank=True)
    status = models.CharField(
        help_text=_('The lifecycle status of this Program.'), max_length=24, null=False, blank=False, db_index=True,
        choices=ProgramStatus.choices, validators=[ProgramStatus.validator]
    )
    marketing_slug = models.CharField(
        help_text=_('Slug used to generate links to the marketing site'), unique=True, max_length=255, db_index=True)
    courses = SortedManyToManyField(Course, related_name='programs')
    order_courses_by_start_date = models.BooleanField(
        default=True, verbose_name='Order Courses By Start Date',
        help_text=_('If this box is not checked, courses will be ordered as in the courses select box above.')
    )
    # NOTE (CCB): Editors of this field should validate the values to ensure only CourseRuns associated
    # with related Courses are stored.
    excluded_course_runs = models.ManyToManyField(CourseRun, blank=True)
    partner = models.ForeignKey(Partner, models.CASCADE, null=True, blank=False)
    overview = models.TextField(null=True, blank=True)
    total_hours_of_effort = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text='Total estimated time needed to complete all courses belonging to this program. This field is '
                  'intended for display on program certificates.')
    # The weeks_to_complete field is now deprecated
    weeks_to_complete = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text=_('This field is now deprecated (ECOM-6021).'
                    'Estimated number of weeks needed to complete a course run belonging to this program.'))
    min_hours_effort_per_week = models.PositiveSmallIntegerField(null=True, blank=True)
    max_hours_effort_per_week = models.PositiveSmallIntegerField(null=True, blank=True)
    authoring_organizations = SortedManyToManyField(Organization, blank=True, related_name='authored_programs')
    banner_image = StdImageField(
        upload_to=UploadToFieldNamePath(populate_from='uuid', path='media/programs/banner_images'),
        blank=True,
        null=True,
        variations={
            'large': (1440, 480),
            'medium': (726, 242),
            'small': (435, 145),
            'x-small': (348, 116),
        },
        render_variations=custom_render_variations
    )
    banner_image_url = models.URLField(null=True, blank=True, help_text='DEPRECATED: Use the banner image field.')
    card_image_url = models.URLField(null=True, blank=True, help_text=_('Image used for discovery cards'))
    video = models.ForeignKey(Video, models.CASCADE, default=None, null=True, blank=True)
    expected_learning_items = SortedManyToManyField(ExpectedLearningItem, blank=True)
    faq = SortedManyToManyField(FAQ, blank=True)
    instructor_ordering = SortedManyToManyField(
        Person,
        blank=True,
        help_text=_('This field can be used by API clients to determine the order in which instructors will be '
                    'displayed on program pages. Instructors in this list should appear before all others associated '
                    'with this programs courses runs.')
    )

    credit_backing_organizations = SortedManyToManyField(
        Organization, blank=True, related_name='credit_backed_programs'
    )
    corporate_endorsements = SortedManyToManyField(CorporateEndorsement, blank=True)
    job_outlook_items = SortedManyToManyField(JobOutlookItem, blank=True)
    individual_endorsements = SortedManyToManyField(Endorsement, blank=True)
    credit_redemption_overview = models.TextField(
        help_text=_('The description of credit redemption for courses in program'),
        blank=True, null=True
    )
    one_click_purchase_enabled = models.BooleanField(
        default=True,
        help_text=_('Allow courses in this program to be purchased in a single transaction')
    )
    hidden = models.BooleanField(
        default=False, db_index=True,
        help_text=_('Hide program on marketing site landing and search pages. This program MAY have a detail page.'))
    enrollment_count = models.IntegerField(
        null=True, blank=True, default=0, help_text=_(
            'Total number of learners who have enrolled in courses this program'
        )
    )
    recent_enrollment_count = models.IntegerField(
        null=True, blank=True, default=0, help_text=_(
            'Total number of learners who have enrolled in courses in this program in the last 6 months'
        )
    )
    objects = ProgramQuerySet.as_manager()

    history = HistoricalRecords()

    def __str__(self):
        return self.title

    def clean(self):
        # See https://stackoverflow.com/questions/47819247
        if self.enrollment_count is None:
            self.enrollment_count = 0
        if self.recent_enrollment_count is None:
            self.recent_enrollment_count = 0

    @property
    def is_program_eligible_for_one_click_purchase(self):
        """
        Checks if the program is eligible for one click purchase.

        To pass the check the program must have one_click_purchase field enabled
        and all its courses must contain only one course run and the remaining
        not excluded course run must contain a purchasable seat.
        """
        if not self.one_click_purchase_enabled:
            return False

        excluded_course_runs = set(self.excluded_course_runs.all())
        applicable_seat_types = self.type.applicable_seat_types.all()

        for course in self.courses.all():
            # Filter the entitlements in python, to avoid duplicate queries for entitlements after prefetching
            all_entitlements = course.entitlements.all()
            entitlement_products = {entitlement for entitlement in all_entitlements
                                    if entitlement.mode in applicable_seat_types}
            if len(entitlement_products) == 1:
                continue

            # Filter the course_runs in python, to avoid duplicate queries for course_runs after prefetching
            all_course_runs = course.course_runs.all()
            course_runs = {course_run for course_run in all_course_runs
                           if course_run.status == CourseRunStatus.Published} - excluded_course_runs

            if len(course_runs) != 1:
                return False

            if not course_runs.pop().enrollable_seats(applicable_seat_types):
                return False

        return True

    @cached_property
    def _course_run_weeks_to_complete(self):
        return [course_run.weeks_to_complete for course_run in self.canonical_course_runs
                if course_run.weeks_to_complete is not None]

    @property
    def weeks_to_complete_min(self):
        return min(self._course_run_weeks_to_complete) if self._course_run_weeks_to_complete else None

    @property
    def weeks_to_complete_max(self):
        return max(self._course_run_weeks_to_complete) if self._course_run_weeks_to_complete else None

    @property
    def marketing_url(self):
        if self.marketing_slug:
            path = '{type}/{slug}'.format(type=self.type.slug.lower(), slug=self.marketing_slug)
            return urljoin(self.partner.marketing_site_url_root, path)

        return None

    @property
    def course_runs(self):
        """
        Warning! Only call this method after retrieving programs from `ProgramSerializer.prefetch_queryset()`.
        Otherwise, this method will incur many, many queries when fetching related courses and course runs.
        """
        excluded_course_run_ids = [course_run.id for course_run in self.excluded_course_runs.all()]

        for course in self.courses.all():
            for run in course.course_runs.all():
                if run.id not in excluded_course_run_ids:
                    yield run

    @property
    def canonical_course_runs(self):
        excluded_course_run_ids = [course_run.id for course_run in self.excluded_course_runs.all()]

        for course in self.courses.all():
            canonical_course_run = course.canonical_course_run
            if canonical_course_run and canonical_course_run.id not in excluded_course_run_ids:
                yield canonical_course_run

    @property
    def languages(self):
        return set(course_run.language for course_run in self.course_runs if course_run.language is not None)

    @property
    def transcript_languages(self):
        languages = [course_run.transcript_languages.all() for course_run in self.course_runs]
        languages = itertools.chain.from_iterable(languages)
        return set(languages)

    @property
    def subjects(self):
        """
        :return: The list of subjects; the first subject should be the most common primary subjects of its courses,
        other subjects should be collected and ranked by frequency among the courses.
        """
        primary_subjects = []
        course_subjects = []
        for course in self.courses.all():
            subjects = course.subjects.all()
            primary_subjects.extend(subjects[:1])  # "Primary" subject is the first one
            course_subjects.extend(subjects)
        common_primary = [s for s, _ in Counter(primary_subjects).most_common()][:1]
        common_others = [s for s, _ in Counter(course_subjects).most_common() if s not in common_primary]
        return common_primary + common_others

    @property
    def topics(self):
        """
        :return: The set of topic tags associated with this program's courses
        """
        topic_set = set()
        for course in self.courses.all():
            topic_set.update(course.topics.all())
        return topic_set

    @property
    def seats(self):
        applicable_seat_types = set(self.type.applicable_seat_types.all())

        for run in self.course_runs:
            for seat in run.seats.all():
                if seat.type in applicable_seat_types:
                    yield seat

    @property
    def canonical_seats(self):
        applicable_seat_types = set(self.type.applicable_seat_types.all())

        for run in self.canonical_course_runs:
            for seat in run.seats.all():
                if seat.type in applicable_seat_types:
                    yield seat

    @property
    def entitlements(self):
        applicable_seat_types = set(self.type.applicable_seat_types.all())
        return CourseEntitlement.objects.filter(mode__in=applicable_seat_types, course__in=self.courses.all())

    @property
    def seat_types(self):
        return set(seat.type for seat in self.seats)

    def _select_for_total_price(self, selected_seat, candidate_seat):
        """
        A helper function to determine which course_run seat is best suitable to be used to calculate
        the program total price. A seat is most suitable if the related course_run is now enrollable,
        has not ended, and the enrollment_start date is most recent
        """
        end_valid = not candidate_seat.course_run.has_ended()

        selected_enrollment_start = selected_seat.course_run.enrollment_start or \
            pytz.utc.localize(datetime.datetime.min)

        # Only select the candidate seat if the candidate seat has no enrollment start,
        # or make sure the candidate course_run is enrollable and
        # the candidate seat enrollment start is most recent
        enrollment_start_valid = candidate_seat.course_run.enrollment_start is None or (
            candidate_seat.course_run.enrollment_start > selected_enrollment_start and
            candidate_seat.course_run.enrollment_start < datetime.datetime.now(pytz.UTC)
        )

        return end_valid and enrollment_start_valid

    def _get_total_price_by_currency(self):
        """
        This helper function returns the total program price indexed by the currency
        """
        currencies_with_total = defaultdict()
        course_map = defaultdict(list)
        for seat in self.canonical_seats:
            course_uuid = seat.course_run.course.uuid
            # Identify the most relevant course_run seat for a course.
            # And use the price of the seat to represent the price of the course
            selected_seats = course_map.get(course_uuid)
            if not selected_seats:
                # If we do not have this course yet, create the seats array
                course_map[course_uuid] = [seat]
            else:
                add_seat = False
                seats_to_remove = []
                for selected_seat in selected_seats:
                    if seat.currency != selected_seat.currency:
                        # If the candidate seat has a different currency than the one in the array,
                        # always add to the array
                        add_seat = True
                    elif self._select_for_total_price(selected_seat, seat):
                        # If the seat has same currency, the course has not ended,
                        # and the course is enrollable, then choose the new seat associated with the course instead,
                        # and mark the original seat in the array to be removed
                        logger.info(
                            "Use course_run {} instead of course_run {} for total program price calculation".format(
                                seat.course_run.key,
                                selected_seat.course_run.key
                            )
                        )
                        add_seat = True
                        seats_to_remove.append(selected_seat)

                if add_seat:
                    course_map[course_uuid].append(seat)
                for removable_seat in seats_to_remove:
                    # Now remove the seats that should not be counted for calculation for program total
                    course_map[course_uuid].remove(removable_seat)

        for entitlement in self.entitlements:
            course_uuid = entitlement.course.uuid
            selected_seats = course_map.get(course_uuid)
            if not selected_seats:
                course_map[course_uuid] = [entitlement]
            else:
                for selected_seat in selected_seats:
                    if entitlement.currency == selected_seat.currency:
                        # If the seat in the array has the same currency as the entitlement,
                        # dont consider it for pricing by remove it from the course_map
                        course_map[course_uuid].remove(selected_seat)
                # Entitlement should be considered for pricing instead of removed seat.
                course_map[course_uuid].append(entitlement)

        # Now calculate the total price of the program indexed by currency
        for course_products in course_map.values():
            for product in course_products:
                current_total = currencies_with_total.get(product.currency, 0)
                current_total += product.price
                currencies_with_total[product.currency] = current_total

        return currencies_with_total

    @property
    def price_ranges(self):
        currencies = defaultdict(list)
        for seat in self.canonical_seats:
            currencies[seat.currency].append(seat.price)
        for entitlement in self.entitlements:
            currencies[entitlement.currency].append(entitlement.price)

        total_by_currency = self._get_total_price_by_currency()

        price_ranges = []
        for currency, prices in currencies.items():
            price_ranges.append({
                'currency': currency.code,
                'min': min(prices),
                'max': max(prices),
                'total': total_by_currency.get(currency, 0)
            })

        return price_ranges

    @property
    def start(self):
        """ Start datetime, calculated by determining the earliest start datetime of all related course runs. """
        if self.course_runs:  # pylint: disable=using-constant-test
            start_dates = [course_run.start for course_run in self.course_runs if course_run.start]

            if start_dates:
                return min(start_dates)

        return None

    @property
    def staff(self):
        staff = [course_run.staff.all() for course_run in self.course_runs]
        staff = itertools.chain.from_iterable(staff)
        return set(staff)

    @property
    def is_active(self):
        return self.status == ProgramStatus.Active

    def save(self, *args, **kwargs):  # pylint: disable=arguments-differ
        suppress_publication = kwargs.pop('suppress_publication', False)
        is_publishable = (
            self.partner.has_marketing_site and
            waffle.switch_is_active('publish_program_to_marketing_site') and
            # Pop to clean the kwargs for the base class save call below
            not suppress_publication
        )

        if is_publishable:
            publisher = ProgramMarketingSitePublisher(self.partner)
            previous_obj = Program.objects.get(id=self.id) if self.id else None

            with transaction.atomic():
                super(Program, self).save(*args, **kwargs)
                publisher.publish_obj(self, previous_obj=previous_obj)
        else:
            super(Program, self).save(*args, **kwargs)


class Ranking(TimeStampedModel):
    """
    Represents the rankings of a program
    """
    rank = models.CharField(max_length=10, verbose_name=_('The actual rank number'))
    description = models.CharField(max_length=255, verbose_name=_('What does the rank number mean'))
    source = models.CharField(max_length=100, verbose_name=_('From where the rank is obtained'))

    def __str__(self):
        return self.description


class Degree(Program):
    """
    This model captures information about a Degree (e.g. a Master's Degree).
    It mostly stores information relevant to the marketing site's product page for this degree.
    """
    apply_url = models.CharField(
        help_text=_('Callback URL to partner application flow'), max_length=255, blank=True
    )
    overall_ranking = models.CharField(
        help_text=_('Overall program ranking (e.g. "#1 in the U.S.")'),
        max_length=255,
        blank=True
    )
    banner_border_color = models.CharField(
        help_text=_("""The 6 character hex value of the color to make the banner borders
            (e.g. "#ff0000" which equals red) No need to provide the `#`"""),
        max_length=6,
        blank=True
    )
    campus_image = models.ImageField(
        upload_to='media/degree_marketing/campus_images/',
        blank=True,
        null=True,
        help_text=_('Provide a campus image for the header of the degree'),
    )
    title_background_image = models.ImageField(
        upload_to='media/degree_marketing/campus_images/',
        blank=True,
        null=True,
        help_text=_('Provide a background image for the title section of the degree'),
    )
    prerequisite_coursework = models.TextField(default='TBD')
    application_requirements = models.TextField(default='TBD')
    costs_fine_print = models.TextField(
        help_text=_('The fine print that displays at the Tuition section\'s bottom'),
        null=True,
        blank=True,
    )
    deadlines_fine_print = models.TextField(
        help_text=_('The fine print that displays at the Deadline section\'s bottom'),
        null=True,
        blank=True,
    )
    rankings = SortedManyToManyField(Ranking, blank=True)

    lead_capture_list_name = models.CharField(
        help_text=_('The sailthru email list name to capture leads'),
        max_length=255,
        default='Master_default',
    )
    lead_capture_image = StdImageField(
        upload_to=UploadToFieldNamePath(populate_from='uuid', path='media/degree_marketing/lead_capture_images/'),
        blank=True,
        null=True,
        variations={
            'large': (1440, 480),
            'medium': (726, 242),
            'small': (435, 145),
            'x-small': (348, 116),
        },
        help_text=_('Please provide an image file for the lead capture banner.'),
    )
    hubspot_lead_capture_form_id = models.CharField(
        help_text=_('The Hubspot form ID for the lead capture form'),
        null=True,
        blank=True,
        max_length=128,
    )

    micromasters_url = models.URLField(
        help_text=_('URL to micromasters landing page'),
        max_length=255,
        blank=True,
        null=True
    )
    micromasters_long_title = models.CharField(
        help_text=_('Micromasters verbose title'),
        max_length=255,
        blank=True,
        null=True
    )
    micromasters_long_description = models.TextField(
        help_text=_('Micromasters descriptive paragraph'),
        blank=True,
        null=True
    )
    micromasters_background_image = StdImageField(
        upload_to=UploadToFieldNamePath(populate_from='uuid', path='media/degree_marketing/mm_images/'),
        blank=True,
        null=True,
        variations={
            'large': (1440, 480),
            'medium': (726, 242),
            'small': (435, 145),
        },
        help_text=_('Customized background image for the MicroMasters section.'),
    )
    micromasters_org_name_override = models.CharField(
        help_text=_(
            'Override org name if micromasters program comes from different organization than Masters program'
        ),
        max_length=50,
        blank=True,
        null=True,
    )
    search_card_ranking = models.CharField(
        help_text=_('Ranking display for search card (e.g. "#1 in the U.S."'),
        max_length=50,
        blank=True,
        null=True,
    )
    search_card_cost = models.CharField(
        help_text=_('Cost display for search card (e.g. "$9,999"'),
        max_length=50,
        blank=True,
        null=True,
    )
    search_card_courses = models.CharField(
        help_text=_('Number of courses for search card (e.g. "11 Courses"'),
        max_length=50,
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name_plural = "Degrees"

    def __str__(self):
        return str('Degree: {}'.format(self.title))


class IconTextPairing(TimeStampedModel):
    """
    Represents an icon:text model
    """
    BELL = 'fa-bell'
    CERTIFICATE = 'fa-certificate'
    CHECK = 'fa-check-circle'
    CLOCK = 'fa-clock-o'
    DESKTOP = 'fa-desktop'
    INFO = 'fa-info-circle'
    SITEMAP = 'fa-sitemap'
    USER = 'fa-user'
    DOLLAR = 'fa-dollar'
    BOOK = 'fa-book'
    MORTARBOARD = 'fa-mortar-board'
    STAR = 'fa-star'
    TROPHY = 'fa-trophy'

    ICON_CHOICES = (
        (BELL, _('Bell')),
        (CERTIFICATE, _('Certificate')),
        (CHECK, _('Checkmark')),
        (CLOCK, _('Clock')),
        (DESKTOP, _('Desktop')),
        (INFO, _('Info')),
        (SITEMAP, _('Sitemap')),
        (USER, _('User')),
        (DOLLAR, _('Dollar')),
        (BOOK, _('Book')),
        (MORTARBOARD, _('Mortar Board')),
        (STAR, _('Star')),
        (TROPHY, _('Trophy')),
    )

    degree = models.ForeignKey(Degree, models.CASCADE, related_name='quick_facts')
    icon = models.CharField(max_length=100, verbose_name=_('Icon FA class'), choices=ICON_CHOICES)
    text = models.CharField(max_length=255, verbose_name=_('Paired text'))

    class Meta:
        verbose_name_plural = "IconTextPairings"

    def __str__(self):
        return str('IconTextPairing: {}'.format(self.text))


class DegreeDeadline(TimeStampedModel):
    """
    DegreeDeadline stores a Degree's important dates. Each DegreeDeadline
    displays in the Degree product page's "Details" section.
    """
    class Meta:
        ordering = ['created']

    degree = models.ForeignKey(Degree, models.CASCADE, related_name='deadlines', null=True)
    semester = models.CharField(
        help_text=_('Deadline applies for this semester (e.g. Spring 2019'),
        max_length=255,
    )
    name = models.CharField(
        help_text=_('Describes the deadline (e.g. Early Admission Deadline)'),
        max_length=255,
    )
    date = models.CharField(
        help_text=_('The date after which the deadline expires (e.g. January 1, 2019)'),
        max_length=255,
    )
    time = models.CharField(
        help_text=_('The time after which the deadline expires (e.g. 11:59 PM EST).'),
        max_length=255,
        blank=True,
    )

    history = HistoricalRecords()

    def __str__(self):
        return "{} {}".format(self.name, self.date)


class DegreeCost(TimeStampedModel):
    """
    Degree cost stores a Degree's associated costs. Each DegreeCost displays in
    a Degree product page's "Details" section.
    """
    class Meta:
        ordering = ['created']

    degree = models.ForeignKey(Degree, models.CASCADE, related_name='costs', null=True)
    description = models.CharField(
        help_text=_('Describes what the cost is for (e.g. Tuition)'),
        max_length=255,
    )
    amount = models.CharField(
        help_text=_('String-based field stating how much the cost is (e.g. $1000).'),
        max_length=255,
    )

    history = HistoricalRecords()

    def __str__(self):
        return str('{}, {}'.format(self.description, self.amount))


class Curriculum(TimeStampedModel):
    """
    This model links a program to the curriculum associated with that program, that is, the
    courses and programs that compose the program.
    """
    uuid = models.UUIDField(blank=True, default=uuid4, editable=False, unique=True, verbose_name=_('UUID'))
    program = models.ForeignKey(
        Program,
        models.CASCADE,
        related_name='curricula',
        null=True,
        default=None,
    )
    name = models.CharField(blank=True, max_length=255)
    is_active = models.BooleanField(default=True)
    marketing_text_brief = NullHtmlField(
        max_length=750,
        help_text=_(
            """A high-level overview of the degree\'s courseware. The "brief"
            text is the first 750 characters of "marketing_text" and must be
            valid HTML."""
        ),
    )
    marketing_text = HtmlField(
        null=True,
        blank=False,
        help_text=_('A high-level overview of the degree\'s courseware.'),
    )
    program_curriculum = models.ManyToManyField(
        Program, through='course_metadata.CurriculumProgramMembership', related_name='degree_program_curricula'
    )
    course_curriculum = models.ManyToManyField(
        Course, through='course_metadata.CurriculumCourseMembership', related_name='degree_course_curricula'
    )

    history = HistoricalRecords()

    def __str__(self):
        return str(self.name) if self.name else str(self.uuid)


class CurriculumProgramMembership(TimeStampedModel):
    """
    Represents the Programs that compose the curriculum of a degree.
    """
    program = models.ForeignKey(Program, models.CASCADE)
    curriculum = models.ForeignKey(Curriculum, models.CASCADE)
    is_active = models.BooleanField(default=True)

    history = HistoricalRecords()


class CurriculumCourseMembership(TimeStampedModel):
    """
    Represents the Courses that compose the curriculum of a degree.
    """
    curriculum = models.ForeignKey(Curriculum, models.CASCADE)
    course = models.ForeignKey(Course, models.CASCADE, related_name='curriculum_course_membership')
    course_run_exclusions = models.ManyToManyField(
        CourseRun, through='course_metadata.CurriculumCourseRunExclusion', related_name='curriculum_course_membership'
    )
    is_active = models.BooleanField(default=True)

    history = HistoricalRecords()

    @property
    def course_runs(self):
        return set(self.course.course_runs.all()) - set(self.course_run_exclusions.all())

    def __str__(self):
        return str(self.curriculum) + " : " + str(self.course)


class CurriculumCourseRunExclusion(TimeStampedModel):
    """
    Represents the CourseRuns that are excluded from a course curriculum.
    """
    course_membership = models.ForeignKey(CurriculumCourseMembership, models.CASCADE)
    course_run = models.ForeignKey(CourseRun, models.CASCADE)

    history = HistoricalRecords()


class Pathway(TimeStampedModel):
    """
    Pathway model
    """
    uuid = models.UUIDField(default=uuid4, editable=False, unique=True, verbose_name=_('UUID'))
    partner = models.ForeignKey(Partner, models.CASCADE, null=True, blank=False)
    name = models.CharField(max_length=255)
    # this field doesn't necessarily map to our normal org models, it's just a convenience field for pathways
    # while we figure them out
    org_name = models.CharField(max_length=255, verbose_name=_("Organization name"))
    email = models.EmailField(blank=True)
    programs = SortedManyToManyField(Program)
    description = models.TextField(null=True, blank=True)
    destination_url = models.URLField(null=True, blank=True)
    pathway_type = models.CharField(
        max_length=32,
        choices=[(tag.value, tag.value) for tag in PathwayType],
        default=PathwayType.CREDIT.value,
    )

    def __str__(self):
        return self.name

    # Define a validation method to be used elsewhere - we can't use it in normal model validation flow because
    # ManyToMany fields are hard to validate (doesn't support validators field kwarg, can't be referenced before
    # first save(), etc). Instead, this method is used in form validation and we rely on that.
    @classmethod
    def validate_partner_programs(cls, partner, programs):
        """ Throws a ValidationError if any program has a different partner than 'partner' """
        bad_programs = [str(x) for x in programs if x.partner != partner]
        if bad_programs:
            msg = _('These programs are for a different partner than the pathway itself: {}')
            raise ValidationError(msg.format(', '.join(bad_programs)))


class PersonSocialNetwork(TimeStampedModel):
    """ Person Social Network model. """
    FACEBOOK = 'facebook'
    TWITTER = 'twitter'
    BLOG = 'blog'
    OTHERS = 'others'

    SOCIAL_NETWORK_CHOICES = {
        FACEBOOK: _('Facebook'),
        TWITTER: _('Twitter'),
        BLOG: _('Blog'),
        OTHERS: _('Others'),
    }

    type = models.CharField(max_length=15, choices=sorted(list(SOCIAL_NETWORK_CHOICES.items())), db_index=True)
    url = models.CharField(max_length=500)
    title = models.CharField(max_length=255, blank=True)
    person = models.ForeignKey(Person, models.CASCADE, related_name='person_networks')

    class Meta:
        verbose_name_plural = 'Person SocialNetwork'

        unique_together = (
            ('person', 'type', 'title'),
        )
        ordering = ['created']

    def __str__(self):
        return '{title}: {url}'.format(title=self.display_title, url=self.url)

    @property
    def display_title(self):
        if self.title:
            return self.title
        elif self.type == self.OTHERS:
            return self.url
        else:
            return self.SOCIAL_NETWORK_CHOICES[self.type]


class PersonAreaOfExpertise(AbstractValueModel):
    """ Person Area of Expertise model. """
    person = models.ForeignKey(Person, models.CASCADE, related_name='areas_of_expertise')

    class Meta:
        verbose_name_plural = 'Person Areas of Expertise'


class CourseUrlSlug(TimeStampedModel):
    course = models.ForeignKey(Course, models.CASCADE, related_name='url_slug_history')
    # need to have these on the model separately for unique_together to work, but it should always match course.partner
    partner = models.ForeignKey(Partner, models.CASCADE)
    url_slug = AutoSlugField(populate_from='course__title', editable=True, slugify_function=uslugify,
                             overwrite_on_add=False, max_length=255)
    is_active = models.BooleanField(default=False)

    # useful if a course editor decides to edit a draft and provide a url_slug that has already been associated
    # with the course
    is_active_on_draft = models.BooleanField(default=False)

    # ensure partner matches course
    def save(self, **kwargs):
        if self.partner != self.course.partner:
            msg = _('Partner {partner_key} and course partner {course_partner_key} do not match when attempting'
                    ' to save url slug {url_slug}')
            raise ValidationError({'partner': [msg.format(partner_key=self.partner.name,
                                                          course_partner_key=self.course.partner.name,
                                                          url_slug=self.url_slug), ]})
        super().save(**kwargs)

    class Meta:
        unique_together = (
            ('partner', 'url_slug')
        )


class CourseUrlRedirect(AbstractValueModel):
    course = models.ForeignKey(Course, models.CASCADE, related_name='url_redirects')
    # need to have these on the model separately for unique_together to work, but it should always match course.partner
    partner = models.ForeignKey(Partner, models.CASCADE)

    def save(self, **kwargs):
        if self.partner != self.course.partner:
            msg = _('Partner {partner_key} and course partner {course_partner_key} do not match when attempting'
                    ' to save url redirect {url_path}')
            raise ValidationError({'partner': [msg.format(partner_key=self.partner.name,
                                                          course_partner_key=self.course.partner.name,
                                                          url_slug=self.value), ]})
        super().save(**kwargs)

    class Meta:
        unique_together = (
            ('partner', 'value')
        )


class BackpopulateCourseTypeConfig(SingletonModel):
    """
    Configuration for the backpopulate_course_type management command.
    """
    class Meta:
        verbose_name = 'backpopulate_course_type argument'

    arguments = models.TextField(
        blank=True,
        help_text='Useful for manually running a Jenkins job. Specify like "--org=key1 --org=key2".',
        default='',
    )

    def __str__(self):
        return self.arguments


class DataLoaderConfig(SingletonModel):
    """
    Configuration for data loaders used in the refresh_course_metadata command.
    """
    max_workers = models.PositiveSmallIntegerField(default=7)


class DeletePersonDupsConfig(SingletonModel):
    """
    Configuration for the delete_person_dups management command.
    """
    class Meta:
        verbose_name = 'delete_person_dups argument'

    arguments = models.TextField(
        blank=True,
        help_text='Useful for manually running a Jenkins job. Specify like "--partner-code=edx A:B C:D".',
        default='',
    )

    def __str__(self):
        return self.arguments


class DrupalPublishUuidConfig(SingletonModel):
    """
    Configuration for data loaders used in the publish_uuids_to_drupal command.
    """
    course_run_ids = models.TextField(default=None, null=False, blank=True, verbose_name=_('Course Run IDs'))
    push_people = models.BooleanField(default=False)


class MigratePublisherToCourseMetadataConfig(SingletonModel):
    """
    Configuration for the migrate_publisher_to_course_metadata command.
    """
    partner = models.ForeignKey(Partner, models.CASCADE, null=True, blank=False)
    orgs = SortedManyToManyField(Organization, blank=True)


class ProfileImageDownloadConfig(SingletonModel):
    """
    Configuration for management command to Download Profile Images from Drupal.
    """
    person_uuids = models.TextField(default=None, null=False, blank=False, verbose_name=_('Profile Image UUIDs'))


class TagCourseUuidsConfig(SingletonModel):
    """
    Configuration for management command add_tag_to_courses.
    """
    tag = models.TextField(default=None, null=True, blank=False, verbose_name=_('Tag'))
    course_uuids = models.TextField(default=None, null=True, blank=False, verbose_name=_('Course UUIDs'))


class MigrateCommentsToSalesforce(SingletonModel):
    """
    Configuration for the migrate_comments_to_salesforce command.
    """
    partner = models.ForeignKey(Partner, models.CASCADE, null=True, blank=False)
    orgs = SortedManyToManyField(Organization, blank=True)


class RemoveRedirectsConfig(SingletonModel):
    """
    Configuration for management command remove_redirects_from_courses.
    """
    remove_all = models.BooleanField(default=False, verbose_name=_('Remove All Redirects'))
    url_paths = models.TextField(default='', null=False, blank=True, verbose_name=_('Url Paths'))
