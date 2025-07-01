import datetime
import logging
try:
    from urllib.parse import urljoin
except:
    from urlparse import urljoin
from uuid import uuid4

import pytz
from django.core.exceptions import ValidationError
from django.conf import settings
from django.db import models
from django.utils.translation import ugettext_lazy as _
from django_extensions.db.fields import AutoSlugField
from django_extensions.db.models import TimeStampedModel
from parler.models import TranslatableModel, TranslatedFieldsModel
from solo.models import SingletonModel
from sortedm2m.fields import SortedManyToManyField
from stdimage.models import StdImageField
from stdimage.utils import UploadToAutoSlug
from taggit_autosuggest.managers import TaggableManager

from course_discovery.apps.core.models import Currency, Partner
from course_discovery.apps.course_metadata.choices import (
    CourseRunStatus,
    ProgramStatus, ProgramVisibility
)
from course_discovery.apps.course_metadata.query import CourseQuerySet, CourseRunQuerySet, ProgramQuerySet
from course_discovery.apps.course_metadata.utils import UploadToFieldNamePath


logger = logging.getLogger(__name__)


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


class AbstractSocialNetworkModel(TimeStampedModel):
    """ SocialNetwork model. """
    FACEBOOK = 'facebook'
    TWITTER = 'twitter'
    BLOG = 'blog'
    OTHERS = 'others'

    SOCIAL_NETWORK_CHOICES = (
        (FACEBOOK, _('Facebook')),
        (TWITTER, _('Twitter')),
        (BLOG, _('Blog')),
        (OTHERS, _('Others')),
    )

    type = models.CharField(max_length=15, choices=SOCIAL_NETWORK_CHOICES, db_index=True)
    value = models.CharField(max_length=500)

    def __str__(self):
        return '{type}: {value}'.format(type=self.type, value=self.value)

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
    pass


class Subject(TranslatableModel, TimeStampedModel):
    """ Subject model. """
    uuid = models.UUIDField(blank=False, null=False, default=uuid4, editable=False, verbose_name=_('UUID'))
    banner_image_url = models.URLField(blank=True, null=True)
    card_image_url = models.URLField(blank=True, null=True)
    slug = AutoSlugField(populate_from='name', editable=True, blank=True,
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
    slug = AutoSlugField(populate_from='name', editable=True, blank=True,
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
        return

    class Meta:
        unique_together = (
            ('partner', 'key'),
            ('partner', 'uuid'),
        )
        ordering = ['created']

    def __str__(self):
        return '{key}: {name}'.format(key=self.key, name=self.name)

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
    profile_image_url = models.URLField(null=True, blank=True)
    profile_image = StdImageField(
        upload_to=UploadToFieldNamePath(populate_from='uuid', path='media/people/profile_images'),
        blank=True,
        null=True,
        variations={
            'medium': (110, 110),
        },
    )
    slug = AutoSlugField(populate_from=('given_name', 'family_name'), editable=True)
    profile_url = models.URLField(null=True, blank=True)
    email = models.EmailField(null=True, blank=True, max_length=255)

    class Meta:
        unique_together = (
            ('partner', 'uuid'),
        )
        verbose_name_plural = _('People')
        ordering = ['created']

    def __str__(self):
        return self.full_name

    def save(self, *args, **kwargs):  # pylint: disable=arguments-differ
        logger.info('Person saved UUID: %s', self.uuid, exc_info=True)
        super(Person, self).save(*args, **kwargs)

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
    def get_profile_image_url(self):
        if self.profile_image and hasattr(self.profile_image, 'url'):
            return self.profile_image.url
        else:
            return self.profile_image_url


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


class Course(TimeStampedModel):
    """ Course model. """
    org = models.CharField(
        max_length=64, null=True, blank=False, db_index=True,
        help_text=_('A organization name')
    )
    uuid = models.UUIDField(default=uuid4, editable=False, verbose_name=_('UUID'))
    canonical_course_run = models.OneToOneField(
        'course_metadata.CourseRun', related_name='canonical_for_course', default=None, null=True, blank=True
    )
    key = models.CharField(max_length=255)
    title = models.CharField(max_length=255, default=None, null=True, blank=True)
    card_image_url = models.URLField(max_length=1024, null=True, blank=True)

    objects = CourseQuerySet.as_manager()

    class Meta:
        unique_together = (
            ('org', 'uuid'),
            ('org', 'key'),
        )
        ordering = ['id']

    def __str__(self):
        return '{key}: {title}'.format(key=self.key, title=self.title)


class LanguageField(models.CharField):
    """Represents a language from the ISO 639-2 language set."""

    def __init__(self, *args, **kwargs):
        """Creates a LanguageField.

        Accepts all the same kwargs as a CharField, except for max_length and
        choices. help_text defaults to a description of the ISO 639-2 set.
        """
        kwargs.pop('max_length', None)
        kwargs.pop('choices', None)
        help_text = kwargs.pop(
            'help_text',
            _("The ISO 639-2 language code for this language."),
        )
        super(LanguageField, self).__init__(
            max_length=16,
            choices=settings.ALL_LANGUAGES,
            help_text=help_text,
            *args,
            **kwargs
        )


class CommaSeparatedLanguagesField(models.CharField):
    description = _("Comma-separated language codes")

    def __init__(self, *args, **kwargs):
        super(CommaSeparatedLanguagesField, self).__init__(*args, **kwargs)

    def to_python(self, value):
        return value.split(',') if value else value

    def from_db_value(self, value, *args, **kwargs):
        return value.split(',') if value else value

    def get_db_prep_value(self, value, *args, **kwargs):
        return ','.join(value) if isinstance(value, list) else value

    def value_to_string(self, obj):
        return self.get_db_prep_value(obj)


class CourseRun(TimeStampedModel):
    """ CourseRun model. """
    uuid = models.UUIDField(default=uuid4, editable=False, verbose_name=_('UUID'))
    course = models.ForeignKey(Course, related_name='course_runs')
    key = models.CharField(max_length=255, unique=True)
    status = models.CharField(
        default=CourseRunStatus.Unpublished, max_length=255, null=False, blank=False,
        db_index=True, choices=CourseRunStatus.choices, validators=[CourseRunStatus.validator]
    )
    title_override = models.CharField(
        max_length=255, default=None, null=True, blank=True,
        help_text=_(
            "Title specific for this run of a course. Leave this value blank to default to the parent course's title."
        )
    )
    start = models.DateTimeField(null=True, blank=True, db_index=True)
    end = models.DateTimeField(null=True, blank=True, db_index=True)
    enrollment_start = models.DateTimeField(null=True, blank=True)
    enrollment_end = models.DateTimeField(null=True, blank=True, db_index=True)

    objects = CourseRunQuerySet.as_manager()

    @property
    def title(self):
        return self.title_override or self.course.title

    @title.setter
    def title(self, value):
        # Treat empty strings as NULL
        value = value or None
        self.title_override = value

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

    def __str__(self):
        return '{key}: {title}'.format(key=self.key, title=self.title)


class SeatType(TimeStampedModel):
    name = models.CharField(max_length=64, unique=True)
    slug = AutoSlugField(populate_from='name')

    def __str__(self):
        return self.name


class Seat(TimeStampedModel):
    """ Seat model. """
    HONOR = 'honor'
    AUDIT = 'audit'
    VERIFIED = 'verified'
    PROFESSIONAL = 'professional'
    CREDIT = 'credit'

    SEAT_TYPES = [HONOR, AUDIT, VERIFIED, PROFESSIONAL, CREDIT]

    # Seat types that may not be purchased without first purchasing another Seat type.
    # EX: 'credit' seats may not be purchased without first purchasing a 'verified' Seat.
    SEATS_WITH_PREREQUISITES = [CREDIT]

    SEAT_TYPE_CHOICES = (
        (HONOR, _('Honor')),
        (AUDIT, _('Audit')),
        (VERIFIED, _('Verified')),
        (PROFESSIONAL, _('Professional')),
        (CREDIT, _('Credit')),
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
            ('course_run', 'type', 'currency', 'credit_provider')
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
    slug = AutoSlugField(populate_from='name', editable=True, unique=True,
                         help_text=_('Leave this field blank to have the value generated automatically.'))

    def __str__(self):
        return self.name


class Program(TimeStampedModel):
    CARD_IMAGES_STORAGE_FOLDER = 'media/programs/card_images'
    CARD_IMAGE_VARIATIONS = {
        'large': (1440, 480),
        'medium': (726, 242),
        'small': (435, 145),
        'x-small': (348, 116),
    }

    uuid = models.UUIDField(blank=True, default=uuid4, editable=False, unique=True, verbose_name=_('UUID'))
    title = models.CharField(
        help_text=_('The user-facing display title for this Program.'), max_length=255, unique=True)
    status = models.CharField(
        help_text=_('The lifecycle status of this Program.'), max_length=24, null=False, blank=False, db_index=True,
        choices=ProgramStatus.choices, validators=[ProgramStatus.validator]
    )
    courses = SortedManyToManyField(Course, related_name='programs')
    orgs = models.CharField(
        max_length=128, null=True, blank=False, db_index=True,
        help_text=_('This field should include all Organizations used by the site. E.g.: orgA+orgB+orgC')
    )
    card_image_url = models.CharField(null=True, blank=True, max_length=1024)
    description = models.TextField(
        default=None, null=True, blank=True,
        help_text=_(
            "Description specific for this program. It would be displayed on the Program's details page."
        )
    )
    duration = models.IntegerField(null=False, blank=False, default=0, help_text=_('Time spend of program'))
    visibility = models.IntegerField(
        null=False, blank=False, default=0,
        choices=ProgramVisibility.choices, validators=[ProgramVisibility.validator],
        help_text=_('Visibility of program')
    )
    languages = CommaSeparatedLanguagesField(max_length=128, null=True, blank=True)
    creator_id = models.IntegerField(
        null=True, blank=False,
        help_text=_('Program Creator(user) id')
    )
    released_date = models.DateTimeField(
        null=True, blank=True,
        help_text=_('Program Released(published) date')
    )

    objects = ProgramQuerySet.as_manager()

    def __str__(self):
        return self.title

    @property
    def marketing_url(self):
        if self.marketing_slug:
            type_node = 'empty_type' if not self.type else self.type.slug.lower()
            path = '{type}/{slug}'.format(type=type_node, slug=self.marketing_slug)
            return urljoin(self.partner.marketing_site_url_root, path)

        return None

    @property
    def course_runs(self):
        """
        Warning! Only call this method after retrieving programs from `ProgramSerializer.prefetch_queryset()`.
        Otherwise, this method will incur many, many queries when fetching related courses and course runs.
        """
        for course in self.courses.all():
            for run in course.course_runs.all():
                yield run

    @property
    def canonical_course_runs(self):
        for course in self.courses.all():
            if course.canonical_course_run:
                yield course.canonical_course_run

    @property
    def start(self):
        """ Start datetime, calculated by determining the earliest start datetime of all related course runs. """
        if not self.course_runs:
            return None

        min_start = None

        for course_run in self.course_runs:
            if not min_start:
                min_start = course_run.start
            elif course_run.start and course_run.start < min_start:
                min_start = course_run.start

        return min_start

    @property
    def end(self):
        if not self.course_runs:
            return None

        max_end = None

        for course_run in self.course_runs:
            if not max_end:
                max_end = course_run.end
            elif course_run.end and course_run.end > max_end:
                max_end = course_run.end

        return max_end

    @property
    def enrollment_start(self):
        if not self.course_runs:
            return None

        min_start = None

        for course_run in self.course_runs:
            if not min_start:
                min_start = course_run.enrollment_start
            elif course_run.enrollment_start and course_run.enrollment_start < min_start:
                min_start = course_run.enrollment_start

        return min_start

    @property
    def enrollment_end(self):
        if not self.course_runs:
            return None

        max_end = None

        for course_run in self.course_runs:
            if not max_end:
                max_end = course_run.enrollment_end
            elif course_run.enrollment_end and course_run.enrollment_end > max_end:
                max_end = course_run.enrollment_end

        return max_end

    @property
    def is_active(self):
        return self.status == ProgramStatus.Active


class PersonSocialNetwork(AbstractSocialNetworkModel):
    """ Person Social Network model. """
    person = models.ForeignKey(Person, related_name='person_networks')

    class Meta(object):
        verbose_name_plural = 'Person SocialNetwork'

        unique_together = (
            ('person', 'type'),
        )
        ordering = ['created']


class CourseRunSocialNetwork(AbstractSocialNetworkModel):
    """ CourseRun Social Network model. """
    course_run = models.ForeignKey(CourseRun, related_name='course_run_networks')

    class Meta(object):
        verbose_name_plural = 'CourseRun SocialNetwork'

        unique_together = (
            ('course_run', 'type'),
        )
        ordering = ['created']


class PersonWork(AbstractValueModel):
    """ Person Works model. """
    person = models.ForeignKey(Person, related_name='person_works')


class DataLoaderConfig(SingletonModel):
    """
    Configuration for data loaders used in the refresh_course_metadata command.
    """
    max_workers = models.PositiveSmallIntegerField(default=7)
