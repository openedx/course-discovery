import datetime
import itertools
import logging
from collections import Counter, defaultdict
from urllib.parse import urljoin
from uuid import uuid4

import pytz
import waffle
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
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
from course_discovery.apps.course_metadata.choices import CourseRunPacing, CourseRunStatus, ProgramStatus, ReportingType
from course_discovery.apps.course_metadata.constants import PathwayType
from course_discovery.apps.course_metadata.managers import DraftManager
from course_discovery.apps.course_metadata.people import MarketingSitePeople
from course_discovery.apps.course_metadata.publishers import (
    CourseRunMarketingSitePublisher, ProgramMarketingSitePublisher
)
from course_discovery.apps.course_metadata.query import CourseQuerySet, CourseRunQuerySet, ProgramQuerySet
from course_discovery.apps.course_metadata.utils import (
    UploadToFieldNamePath, clean_query, custom_render_variations, uslugify
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
    draft_version = models.OneToOneField('self', models.CASCADE, null=True, blank=True,
                                         related_name='official_version', limit_choices_to={'draft': True})

    everything = models.Manager()
    objects = DraftManager()

    class Meta(object):
        abstract = True


class AbstractNamedModel(TimeStampedModel):
    """ Abstract base class for models with only a name field. """
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name

    class Meta(object):
        abstract = True


class AbstractValueModel(TimeStampedModel):
    """ Abstract base class for models with only a value field. """
    value = models.CharField(max_length=255)

    def __str__(self):
        return self.value

    class Meta(object):
        abstract = True


class AbstractMediaModel(TimeStampedModel):
    """ Abstract base class for media-related (e.g. image, video) models. """
    src = models.URLField(max_length=255, unique=True)
    description = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.src

    class Meta(object):
        abstract = True


class AbstractTitleDescriptionModel(TimeStampedModel):
    """ Abstract base class for models with a title and description pair. """
    title = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        if self.title:
            return self.title
        return self.description

    class Meta(object):
        abstract = True


class Image(AbstractMediaModel):
    """ Image model. """
    height = models.IntegerField(null=True, blank=True)
    width = models.IntegerField(null=True, blank=True)


class Video(AbstractMediaModel):
    """ Video model. """
    image = models.ForeignKey(Image, null=True, blank=True)

    def __str__(self):
        return '{src}: {description}'.format(src=self.src, description=self.description)


class LevelType(AbstractNamedModel):
    """ LevelType model. """
    order = models.PositiveSmallIntegerField(default=0, db_index=True)

    class Meta:
        ordering = ('order',)


class Subject(TranslatableModel, TimeStampedModel):
    """ Subject model. """
    uuid = models.UUIDField(blank=False, null=False, default=uuid4, editable=False, verbose_name=_('UUID'))
    banner_image_url = models.URLField(blank=True, null=True)
    card_image_url = models.URLField(blank=True, null=True)
    slug = AutoSlugField(populate_from='name', editable=True, blank=True, slugify_function=uslugify,
                         help_text=_('Leave this field blank to have the value generated automatically.'))

    partner = models.ForeignKey(Partner)

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


class SubjectTranslation(TranslatedFieldsModel):
    master = models.ForeignKey(Subject, related_name='translations', null=True)

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

    partner = models.ForeignKey(Partner)

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


class TopicTranslation(TranslatedFieldsModel):
    master = models.ForeignKey(Topic, related_name='translations', null=True)

    name = models.CharField(max_length=255, blank=False, null=False)
    subtitle = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    long_description = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ('language_code', 'master')
        verbose_name = _('Topic model translations')


class Prerequisite(AbstractNamedModel):
    """ Prerequisite model. """
    pass


class ExpectedLearningItem(AbstractValueModel):
    """ ExpectedLearningItem model. """
    pass


class JobOutlookItem(AbstractValueModel):
    """ JobOutlookItem model. """
    pass


class SyllabusItem(AbstractValueModel):
    """ SyllabusItem model. """
    parent = models.ForeignKey('self', blank=True, null=True, related_name='children')


class AdditionalPromoArea(AbstractTitleDescriptionModel):
    """ Additional Promo Area Model """
    pass


class Organization(TimeStampedModel):
    """ Organization model. """
    partner = models.ForeignKey(Partner, null=True, blank=False)
    uuid = models.UUIDField(blank=False, null=False, default=uuid4, editable=False, verbose_name=_('UUID'))
    key = models.CharField(max_length=255, help_text=_('Please do not use any spaces or special characters other '
                                                       'than period, underscore or hyphen. This key will be used '
                                                       'in the course\'s course key.'))
    name = models.CharField(max_length=255)
    marketing_url_path = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    homepage_url = models.URLField(max_length=255, null=True, blank=True)
    logo_image_url = models.URLField(null=True, blank=True)
    banner_image_url = models.URLField(null=True, blank=True)
    certificate_logo_image_url = models.URLField(
        null=True, blank=True, help_text=_('Logo to be displayed on certificates. If this logo is the same as '
                                           'logo_image_url, copy and paste the same value to both fields.')
    )

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
        if self.marketing_url_path:
            return urljoin(self.partner.marketing_site_url_root, self.marketing_url_path)

        return None


class Person(TimeStampedModel):
    """ Person model. """
    uuid = models.UUIDField(blank=False, null=False, default=uuid4, editable=False, verbose_name=_('UUID'))
    partner = models.ForeignKey(Partner, null=True, blank=False)
    salutation = models.CharField(max_length=10, null=True, blank=True)
    given_name = models.CharField(max_length=255)
    family_name = models.CharField(max_length=255, null=True, blank=True)
    bio = models.TextField(null=True, blank=True)
    bio_language = models.ForeignKey(LanguageTag, null=True, blank=True)
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
    major_works = models.TextField(
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
    person = models.OneToOneField(Person)
    title = models.CharField(max_length=255)
    organization = models.ForeignKey(Organization, null=True, blank=True)
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


class Course(DraftModelMixin, PkSearchableMixin, TimeStampedModel):
    """ Course model. """
    partner = models.ForeignKey(Partner)
    uuid = models.UUIDField(default=uuid4, editable=False, verbose_name=_('UUID'))
    canonical_course_run = models.OneToOneField(
        'course_metadata.CourseRun', related_name='canonical_for_course', default=None, null=True, blank=True
    )
    key = models.CharField(max_length=255, db_index=True)
    title = models.CharField(max_length=255, default=None, null=True, blank=True)
    short_description = models.TextField(default=None, null=True, blank=True)
    full_description = models.TextField(default=None, null=True, blank=True)
    extra_description = models.ForeignKey(
        AdditionalPromoArea, default=None, null=True, blank=True, related_name='extra_description'
    )
    authoring_organizations = SortedManyToManyField(Organization, blank=True, related_name='authored_courses')
    sponsoring_organizations = SortedManyToManyField(Organization, blank=True, related_name='sponsored_courses')
    subjects = SortedManyToManyField(Subject, blank=True)
    prerequisites = models.ManyToManyField(Prerequisite, blank=True)
    level_type = models.ForeignKey(LevelType, default=None, null=True, blank=True)
    expected_learning_items = SortedManyToManyField(ExpectedLearningItem, blank=True)
    outcome = models.TextField(blank=True, null=True)
    prerequisites_raw = models.TextField(blank=True, null=True)
    syllabus_raw = models.TextField(blank=True, null=True)
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
    video = models.ForeignKey(Video, default=None, null=True, blank=True)
    faq = models.TextField(default=None, null=True, blank=True, verbose_name=_('FAQ'))
    learner_testimonials = models.TextField(default=None, null=True, blank=True)
    has_ofac_restrictions = models.BooleanField(default=False, verbose_name=_('Course Has OFAC Restrictions'))
    enrollment_count = models.IntegerField(
        null=True, blank=True, default=0, help_text=_('Total number of learners who have enrolled in this course')
    )
    recent_enrollment_count = models.IntegerField(
        null=True, blank=True, default=0, help_text=_(
            'Total number of learners who have enrolled in this course in the last 6 months'
        )
    )

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

    additional_information = models.TextField(
        default=None, null=True, blank=True, verbose_name=_('Additional Information')
    )

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
    def active_course_runs(self):
        """ Returns course runs that have not yet ended and meet the following enrollment criteria:
            - Open for enrollment
            - OR will be open for enrollment in the future
            - OR have no specified enrollment close date (e.g. self-paced courses)

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


class CourseEditor(TimeStampedModel):
    """
    CourseEditor model, defining who can edit a course and its course runs.

    .. no_pii:
    """
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='courses_edited')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='editors')

    class Meta(object):
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
    def is_course_editable(cls, user, course):
        if user.is_staff:
            return True

        authoring_orgs = course.authoring_organizations.all()

        # No matter what, if an editor or their organization has been removed from the course, they can't be an editor
        # for it. This handles cases of being dropped from an org... But might be too restrictive in case we want
        # to allow outside guest editors on a course? Let's try this for now and see how it goes.
        valid_editors = course.editors.filter(user__groups__organization_extension__organization__in=authoring_orgs)

        if not valid_editors.exists():
            # No valid editors - this is an edge case where we just grant anyone in an authoring org access
            return user.groups.filter(organization_extension__organization__in=authoring_orgs).exists()
        else:
            return user in {x.user for x in valid_editors}

    @classmethod
    def editable_courses(cls, user, queryset):
        if user.is_staff:
            return queryset

        user_orgs = Organization.objects.filter(organization_extension__group__in=user.groups.all())
        has_valid_editors = Q(
            editors__user__groups__organization_extension__organization__in=F('authoring_organizations')
        )
        has_user_editor = Q(editors__user=user)
        return queryset.filter(has_user_editor | ~has_valid_editors, authoring_organizations__in=user_orgs)

    @classmethod
    def editable_course_runs(cls, user, queryset):
        if user.is_staff:
            return queryset

        user_orgs = Organization.objects.filter(organization_extension__group__in=user.groups.all())
        has_valid_editors = Q(
            course__editors__user__groups__organization_extension__organization__in=F('course__authoring_organizations')
        )
        has_user_editor = Q(course__editors__user=user)
        return queryset.filter(has_user_editor | ~has_valid_editors, course__authoring_organizations__in=user_orgs)


class CourseRun(DraftModelMixin, PkSearchableMixin, TimeStampedModel):
    """ CourseRun model. """
    uuid = models.UUIDField(default=uuid4, editable=False, verbose_name=_('UUID'))
    course = models.ForeignKey(Course, related_name='course_runs')
    key = models.CharField(max_length=255)
    status = models.CharField(default=CourseRunStatus.Unpublished, max_length=255, null=False, blank=False,
                              db_index=True, choices=CourseRunStatus.choices, validators=[CourseRunStatus.validator])
    title_override = models.CharField(
        max_length=255, default=None, null=True, blank=True,
        help_text=_(
            "Title specific for this run of a course. Leave this value blank to default to the parent course's title."))
    start = models.DateTimeField(null=True, blank=True, db_index=True)
    end = models.DateTimeField(null=True, blank=True, db_index=True)
    enrollment_start = models.DateTimeField(null=True, blank=True)
    enrollment_end = models.DateTimeField(null=True, blank=True, db_index=True)
    announcement = models.DateTimeField(null=True, blank=True)
    short_description_override = models.TextField(
        default=None, null=True, blank=True,
        help_text=_(
            "Short description specific for this run of a course. Leave this value blank to default to "
            "the parent course's short_description attribute."))
    full_description_override = models.TextField(
        default=None, null=True, blank=True,
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
    language = models.ForeignKey(LanguageTag, null=True, blank=True)
    transcript_languages = models.ManyToManyField(LanguageTag, blank=True, related_name='transcript_courses')
    pacing_type = models.CharField(max_length=255, db_index=True, null=True, blank=True,
                                   choices=CourseRunPacing.choices, validators=[CourseRunPacing.validator])
    syllabus = models.ForeignKey(SyllabusItem, default=None, null=True, blank=True)
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
    video = models.ForeignKey(Video, default=None, null=True, blank=True)
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
    outcome_override = models.TextField(
        default=None, blank=True, null=True,
        help_text=_(
            "'What You Will Learn' description for this particular course run. Leave this value blank to default "
            "to the parent course's Outcome attribute."))

    tags = TaggableManager(
        blank=True,
        help_text=_('Pick a tag from the suggestions. To make a new tag, add a comma after the tag name.'),
    )

    has_ofac_restrictions = models.BooleanField(
        default=False,
        verbose_name=_('Add OFAC restriction text to the FAQ section of the Marketing site')
    )

    everything = CourseRunQuerySet.as_manager()
    objects = DraftManager.from_queryset(CourseRunQuerySet)()

    class Meta:
        unique_together = (
            ('key', 'draft'),
        )

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
            if seat.type not in Seat.SEATS_WITH_PREREQUISITES and seat.price > 0.0:
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

        # An unenrolled user may not enroll and purchase paid seats after the course has ended.
        deadline = self.end

        # An unenrolled user may not enroll and purchase paid seats after enrollment has ended.
        if self.enrollment_end and (deadline is None or self.enrollment_end < deadline):
            deadline = self.enrollment_end

        # Note that even though we're sorting in descending order by upgrade_deadline, we will need to look at
        # both the first and last record in the result set to determine which Seat has the latest upgrade_deadline.
        # We consider Null values to be > than non-Null values, and Null values may sort to the top or bottom of
        # the result set, depending on the DB backend.
        latest_seat = seats[-1] if seats[-1].upgrade_deadline is None else seats[0]
        if latest_seat.upgrade_deadline and (deadline is None or latest_seat.upgrade_deadline < deadline):
            deadline = latest_seat.upgrade_deadline

        return deadline

    def enrollable_seats(self, types=None):
        """
        Returns seats, of the given type(s), that can be enrolled in/purchased.

        Arguments:
            types (list of seat type names): Type of seats to limit the returned value to.

        Returns:
            List of Seats
        """
        now = datetime.datetime.now(pytz.UTC)
        enrollable_seats = []

        if self.end and now > self.end:
            return enrollable_seats

        if self.enrollment_start and self.enrollment_start > now:
            return enrollable_seats

        if self.enrollment_end and now > self.enrollment_end:
            return enrollable_seats

        types = types or Seat.SEAT_TYPES
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
        return self.course.programs

    @property
    def seat_types(self):
        return [seat.type for seat in self.seats.all()]

    @property
    def type(self):
        seat_types = set(self.seat_types)
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

        logger.debug('Unable to determine type for course run [%s]. Seat types are [%s]', self.key, seat_types)
        return None

    @property
    def level_type(self):
        return self.course.level_type

    @property
    def availability(self):
        now = datetime.datetime.now(pytz.UTC)
        upcoming_cutoff = now + datetime.timedelta(days=60)

        if self.end and self.end <= now:
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

    def __str__(self):
        return '{key}: {title}'.format(key=self.key, title=self.title)

    def save(self, *args, **kwargs):  # pylint: disable=arguments-differ
        is_new_course_run = not self.pk
        suppress_publication = kwargs.pop('suppress_publication', False)
        is_publishable = (
            self.course.partner.has_marketing_site and
            waffle.switch_is_active('publish_course_runs_to_marketing_site') and
            # Pop to clean the kwargs for the base class save call below
            not suppress_publication and
            not self.draft
        )

        if is_publishable:
            publisher = CourseRunMarketingSitePublisher(self.course.partner)
            previous_obj = CourseRun.objects.get(id=self.id) if self.id else None

            if not self.slug and self.id:
                # If we are publishing this object to marketing site, let's make sure slug is defined.
                # Nowadays slugs will be defined at creation time by AutoSlugField for us, so we only need this code
                # path for database rows that were empty before we started using AutoSlugField.
                self.slug = CourseRun._meta.get_field('slug').create_slug(self, True)

            with transaction.atomic():
                super(CourseRun, self).save(*args, **kwargs)
                publisher.publish_obj(self, previous_obj=previous_obj)
        else:
            super(CourseRun, self).save(*args, **kwargs)

        if is_new_course_run:
            retired_programs = self.programs.filter(status=ProgramStatus.Retired)
            for program in retired_programs:
                program.excluded_course_runs.add(self)


class SeatType(TimeStampedModel):
    name = models.CharField(max_length=64, unique=True)
    slug = AutoSlugField(populate_from='name', slugify_function=uslugify)

    def __str__(self):
        return self.name


class Seat(DraftModelMixin, TimeStampedModel):
    """ Seat model. """
    HONOR = 'honor'
    AUDIT = 'audit'
    VERIFIED = 'verified'
    PROFESSIONAL = 'professional'
    CREDIT = 'credit'
    MASTERS = 'masters'

    SEAT_TYPES = [HONOR, AUDIT, VERIFIED, PROFESSIONAL, CREDIT, MASTERS]
    ENTITLEMENT_MODES = [VERIFIED, PROFESSIONAL]

    # Seat types that may not be purchased without first purchasing another Seat type.
    # EX: 'credit' seats may not be purchased without first purchasing a 'verified' Seat.
    SEATS_WITH_PREREQUISITES = [CREDIT]

    SEAT_TYPE_CHOICES = (
        (HONOR, _('Honor')),
        (AUDIT, _('Audit')),
        (VERIFIED, _('Verified')),
        (PROFESSIONAL, _('Professional')),
        (CREDIT, _('Credit')),
        (MASTERS, _('Masters')),
    )

    PRICE_FIELD_CONFIG = {
        'decimal_places': 2,
        'max_digits': 10,
        'null': False,
        'default': 0.00,
    }
    course_run = models.ForeignKey(CourseRun, related_name='seats')
    # TODO Replace with FK to SeatType model
    type = models.CharField(max_length=63, choices=SEAT_TYPE_CHOICES)
    price = models.DecimalField(**PRICE_FIELD_CONFIG)
    currency = models.ForeignKey(Currency)
    upgrade_deadline = models.DateTimeField(null=True, blank=True)
    credit_provider = models.CharField(max_length=255, null=True, blank=True)
    credit_hours = models.IntegerField(null=True, blank=True)
    sku = models.CharField(max_length=128, null=True, blank=True)
    bulk_sku = models.CharField(max_length=128, null=True, blank=True)

    class Meta(object):
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
    course = models.ForeignKey(Course, related_name='entitlements')
    mode = models.ForeignKey(SeatType)
    partner = models.ForeignKey(Partner, null=True, blank=False)
    price = models.DecimalField(**PRICE_FIELD_CONFIG)
    currency = models.ForeignKey(Currency, default='USD')
    sku = models.CharField(max_length=128, null=True, blank=True)
    expires = models.DateTimeField(null=True, blank=True)

    class Meta(object):
        unique_together = (
            ('course', 'mode', 'draft')
        )
        ordering = ['created']


class Endorsement(TimeStampedModel):
    endorser = models.ForeignKey(Person, blank=False, null=False)
    quote = models.TextField(blank=False, null=False)

    def __str__(self):
        return self.endorser.full_name


class CorporateEndorsement(TimeStampedModel):
    corporation_name = models.CharField(max_length=128, blank=False, null=False)
    statement = models.TextField(null=True, blank=True)
    image = models.ForeignKey(Image, blank=True, null=True)
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


class ProgramType(TimeStampedModel):
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

    def __str__(self):
        return self.name


class Program(PkSearchableMixin, TimeStampedModel):
    uuid = models.UUIDField(blank=True, default=uuid4, editable=False, unique=True, verbose_name=_('UUID'))
    title = models.CharField(
        help_text=_('The user-facing display title for this Program.'), max_length=255, unique=True)
    subtitle = models.CharField(
        help_text=_('A brief, descriptive subtitle for the Program.'), max_length=255, blank=True)
    type = models.ForeignKey(ProgramType, null=True, blank=True)
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
    partner = models.ForeignKey(Partner, null=True, blank=False)
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
    video = models.ForeignKey(Video, default=None, null=True, blank=True)
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
        applicable_seat_types = [seat_type.name.lower() for seat_type in self.type.applicable_seat_types.all()]

        for course in self.courses.all():
            entitlement_products = set(course.entitlements.filter(mode__name__in=applicable_seat_types).exclude(
                expires__lte=datetime.datetime.now(pytz.UTC)))
            if len(entitlement_products) == 1:
                continue

            course_runs = set(course.course_runs.filter(status=CourseRunStatus.Published)) - excluded_course_runs

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
        applicable_seat_types = set(seat_type.slug for seat_type in self.type.applicable_seat_types.all())

        for run in self.course_runs:
            for seat in run.seats.all():
                if seat.type in applicable_seat_types:
                    yield seat

    @property
    def canonical_seats(self):
        applicable_seat_types = set(seat_type.slug for seat_type in self.type.applicable_seat_types.all())

        for run in self.canonical_course_runs:
            for seat in run.seats.all():
                if seat.type in applicable_seat_types:
                    yield seat

    @property
    def entitlements(self):
        applicable_seat_types = set(seat_type.slug for seat_type in self.type.applicable_seat_types.all())
        return CourseEntitlement.objects.filter(mode__name__in=applicable_seat_types, course__in=self.courses.all())

    @property
    def seat_types(self):
        return set(seat.type for seat in self.seats)

    def _select_for_total_price(self, selected_seat, candidate_seat):
        """
        A helper function to determine which course_run seat is best suitable to be used to calculate
        the program total price. A seat is most suitable if the related course_run is now enrollable,
        has not ended, and the enrollment_start date is most recent
        """
        end_valid = candidate_seat.course_run.end is None or \
            candidate_seat.course_run.end >= datetime.datetime.now(pytz.UTC)

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
        if self.course_runs:
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
    search_card_ranking = models.CharField(
        help_text=_('Ranking display for search card (e.g. "#1 in the U.S."'),
        max_length=50,
        blank=True,
        null=True
    )
    search_card_cost = models.CharField(
        help_text=_('Cost display for search card (e.g. "$9,999"'),
        max_length=50,
        blank=True,
        null=True
    )
    search_card_courses = models.CharField(
        help_text=_('Number of courses for search card (e.g. "11 Courses"'),
        max_length=50,
        blank=True,
        null=True
    )

    class Meta(object):
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

    degree = models.ForeignKey(Degree, related_name='quick_facts', on_delete=models.CASCADE)
    icon = models.CharField(max_length=100, verbose_name=_('Icon FA class'), choices=ICON_CHOICES)
    text = models.CharField(max_length=255, verbose_name=_('Paired text'))

    class Meta(object):
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

    degree = models.ForeignKey(Degree, on_delete=models.CASCADE, related_name='deadlines', null=True)
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

    degree = models.ForeignKey(Degree, on_delete=models.CASCADE, related_name='costs', null=True)
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
        on_delete=models.CASCADE,
        related_name='curricula',
        null=True,
        default=None,
    )
    name = models.CharField(blank=True, max_length=255)
    is_active = models.BooleanField(default=True)
    marketing_text_brief = models.TextField(
        null=True,
        blank=True,
        max_length=750,
        help_text=_(
            """A high-level overview of the degree\'s courseware. The "brief"
            text is the first 750 characters of "marketing_text" and must be
            valid HTML."""
        ),
    )
    marketing_text = models.TextField(
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
    program = models.ForeignKey(Program, on_delete=models.CASCADE)
    curriculum = models.ForeignKey(Curriculum, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)

    history = HistoricalRecords()


class CurriculumCourseMembership(TimeStampedModel):
    """
    Represents the Courses that compose the curriculum of a degree.
    """
    curriculum = models.ForeignKey(Curriculum, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='curriculum_course_membership')
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
    course_membership = models.ForeignKey(CurriculumCourseMembership, on_delete=models.CASCADE)
    course_run = models.ForeignKey(CourseRun, on_delete=models.CASCADE)

    history = HistoricalRecords()


class Pathway(TimeStampedModel):
    """
    Pathway model
    """
    uuid = models.UUIDField(default=uuid4, editable=False, unique=True, verbose_name=_('UUID'))
    partner = models.ForeignKey(Partner, null=True, blank=False)
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
            raise ValidationError(msg.format(', '.join(bad_programs)))  # pylint: disable=no-member


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
    person = models.ForeignKey(Person, related_name='person_networks')

    class Meta(object):
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
    person = models.ForeignKey(Person, related_name='areas_of_expertise')

    class Meta(object):
        verbose_name_plural = 'Person Areas of Expertise'


class DataLoaderConfig(SingletonModel):
    """
    Configuration for data loaders used in the refresh_course_metadata command.
    """
    max_workers = models.PositiveSmallIntegerField(default=7)


class DeletePersonDupsConfig(SingletonModel):
    """
    Configuration for the delete_person_dups management command.
    """
    class Meta(object):
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


class ProfileImageDownloadConfig(SingletonModel):
    """
    Configuration for management command to Download Profile Images from Drupal.
    """
    person_uuids = models.TextField(default=None, null=False, blank=False, verbose_name=_('Profile Image UUIDs'))
