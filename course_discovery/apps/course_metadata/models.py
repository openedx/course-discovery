import datetime
import itertools
import logging
from collections import defaultdict
from urllib.parse import urljoin
from uuid import uuid4

import pytz
import waffle
from django.db import models, transaction
from django.db.models.query_utils import Q
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from django_extensions.db.fields import AutoSlugField
from django_extensions.db.models import TimeStampedModel
from haystack import connections
from haystack.query import SearchQuerySet
from sortedm2m.fields import SortedManyToManyField
from stdimage.models import StdImageField
from stdimage.utils import UploadToAutoSlug
from taggit_autosuggest.managers import TaggableManager

from course_discovery.apps.core.models import Currency, Partner
from course_discovery.apps.course_metadata.choices import CourseRunStatus, CourseRunPacing, ProgramStatus
from course_discovery.apps.course_metadata.publishers import MarketingSitePublisher
from course_discovery.apps.course_metadata.query import CourseQuerySet, CourseRunQuerySet, ProgramQuerySet
from course_discovery.apps.course_metadata.utils import UploadToFieldNamePath
from course_discovery.apps.course_metadata.utils import clean_query, custom_render_variations
from course_discovery.apps.ietf_language_tags.models import LanguageTag

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


class Subject(TimeStampedModel):
    """ Subject model. """
    uuid = models.UUIDField(blank=False, null=False, default=uuid4, editable=False, verbose_name=_('UUID'))
    name = models.CharField(max_length=255, blank=False, null=False)
    subtitle = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    banner_image_url = models.URLField(blank=True, null=True)
    card_image_url = models.URLField(blank=True, null=True)
    slug = AutoSlugField(populate_from='name', editable=True, blank=True,
                         help_text=_('Leave this field blank to have the value generated automatically.'))
    partner = models.ForeignKey(Partner)

    def __str__(self):
        return self.name

    class Meta:
        unique_together = (
            ('partner', 'name'),
            ('partner', 'slug'),
            ('partner', 'uuid'),
        )


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
    key = models.CharField(max_length=255)
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

    class Meta:
        unique_together = (
            ('partner', 'key'),
            ('partner', 'uuid'),
        )

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
    given_name = models.CharField(max_length=255)
    family_name = models.CharField(max_length=255, null=True, blank=True)
    bio = models.TextField(null=True, blank=True)
    profile_image_url = models.URLField(null=True, blank=True)
    profile_image = StdImageField(
        upload_to=UploadToAutoSlug(populate_from='uuid', path='media/people/profile_images'),
        blank=True,
        null=True,
        variations={
            'medium': (110, 110),
        },
    )
    slug = AutoSlugField(populate_from=('given_name', 'family_name'), editable=True)

    class Meta:
        unique_together = (
            ('partner', 'uuid'),
        )
        verbose_name_plural = _('People')

    def __str__(self):
        return self.full_name

    @property
    def full_name(self):
        return ' '.join((self.given_name, self.family_name,))


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
    partner = models.ForeignKey(Partner)
    uuid = models.UUIDField(default=uuid4, editable=False, verbose_name=_('UUID'))
    canonical_course_run = models.OneToOneField(
        'course_metadata.CourseRun', related_name='canonical_for_course', default=None, null=True, blank=True
    )
    key = models.CharField(max_length=255)
    title = models.CharField(max_length=255, default=None, null=True, blank=True)
    short_description = models.CharField(max_length=255, default=None, null=True, blank=True)
    full_description = models.TextField(default=None, null=True, blank=True)
    authoring_organizations = SortedManyToManyField(Organization, blank=True, related_name='authored_courses')
    sponsoring_organizations = SortedManyToManyField(Organization, blank=True, related_name='sponsored_courses')
    subjects = models.ManyToManyField(Subject, blank=True)
    prerequisites = models.ManyToManyField(Prerequisite, blank=True)
    level_type = models.ForeignKey(LevelType, default=None, null=True, blank=True)
    expected_learning_items = SortedManyToManyField(ExpectedLearningItem, blank=True)
    card_image_url = models.URLField(null=True, blank=True)
    slug = AutoSlugField(populate_from='key', editable=True)
    video = models.ForeignKey(Video, default=None, null=True, blank=True)
    number = models.CharField(
        max_length=50, null=True, blank=True, help_text=_(
            'Course number format e.g CS002x, BIO1.1x, BIO1.2x'
        )
    )

    objects = CourseQuerySet.as_manager()

    class Meta:
        unique_together = (
            ('partner', 'uuid'),
            ('partner', 'key'),
        )

    def __str__(self):
        return '{key}: {title}'.format(key=self.key, title=self.title)

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

    @classmethod
    def search(cls, query):
        """ Queries the search index.

        Args:
            query (str) -- Elasticsearch querystring (e.g. `title:intro*`)

        Returns:
            QuerySet
        """
        query = clean_query(query)
        results = SearchQuerySet().models(cls).raw_search(query)
        ids = [result.pk for result in results]
        return cls.objects.filter(pk__in=ids)

    def save(self, *args, **kwargs):
        super(Course, self).save(*args, **kwargs)
        try:
            self.reindex_course_runs()
        except Exception:  # pylint: disable=broad-except
            logger.exception("An error occurred while attempting to reindex the course runs"
                             "of Course with key: [{key}].".format(key=self.key))

    def reindex_course_runs(self):
        index = connections['default'].get_unified_index().get_index(CourseRun)
        for course_run in self.course_runs.all():
            index.update_object(course_run)


class CourseRun(TimeStampedModel):
    """ CourseRun model. """

    uuid = models.UUIDField(default=uuid4, editable=False, verbose_name=_('UUID'))
    course = models.ForeignKey(Course, related_name='course_runs')
    key = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=255, null=False, blank=False, db_index=True, choices=CourseRunStatus.choices,
                              validators=[CourseRunStatus.validator])
    title_override = models.CharField(
        max_length=255, default=None, null=True, blank=True,
        help_text=_(
            "Title specific for this run of a course. Leave this value blank to default to the parent course's title."))
    start = models.DateTimeField(null=True, blank=True, db_index=True)
    end = models.DateTimeField(null=True, blank=True, db_index=True)
    enrollment_start = models.DateTimeField(null=True, blank=True)
    enrollment_end = models.DateTimeField(null=True, blank=True, db_index=True)
    announcement = models.DateTimeField(null=True, blank=True)
    short_description_override = models.CharField(
        max_length=255, default=None, null=True, blank=True,
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
    card_image_url = models.URLField(null=True, blank=True)
    video = models.ForeignKey(Video, default=None, null=True, blank=True)
    slug = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    hidden = models.BooleanField(default=False)
    mobile_available = models.BooleanField(default=False)
    course_overridden = models.BooleanField(
        default=False,
        help_text=_('Indicates whether the course relation has been manually overridden.')
    )

    tags = TaggableManager(
        blank=True,
        help_text=_('Pick a tag from the suggestions. To make a new tag, add a comma after the tag name.'),
    )

    objects = CourseRunQuerySet.as_manager()

    def _enrollable_paid_seats(self):
        """
        Return a QuerySet that may be used to fetch the enrollable paid Seats (Seats with price > 0 and no
        prerequisites) associated with this CourseRun.
        """
        return self.seats.exclude(type__in=Seat.SEATS_WITH_PREREQUISITES).filter(price__gt=0.0)

    def has_enrollable_paid_seats(self):
        """
        Return a boolean indicating whether or not enrollable paid Seats (Seats with price > 0 and no prerequisites)
        are available for this CourseRun.
        """
        return len(self._enrollable_paid_seats()[:1]) > 0

    def get_paid_seat_enrollment_end(self):
        """
        Return the final date for which an unenrolled user may enroll and purchase a paid Seat for this CourseRun, or
        None if the date is unknown or enrollable paid Seats are not available.
        """
        seats = list(self._enrollable_paid_seats().order_by('-upgrade_deadline'))
        if len(seats) == 0:
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
        elif self.start and self.end and (self.start <= now < self.end):
            return _('Current')
        elif self.start and (now < self.start < upcoming_cutoff):
            return _('Starting Soon')
        else:
            return _('Upcoming')

    @classmethod
    def search(cls, query):
        """ Queries the search index.

        Args:
            query (str) -- Elasticsearch querystring (e.g. `title:intro*`)

        Returns:
            SearchQuerySet
        """
        query = clean_query(query)
        return SearchQuerySet().models(cls).raw_search(query).load_all()

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

    class Meta(object):
        unique_together = (
            ('course_run', 'type', 'currency', 'credit_provider')
        )


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
    slug = AutoSlugField(populate_from='name', editable=True, blank=True,
                         help_text=_('Leave this field blank to have the value generated automatically.'))

    def __str__(self):
        return self.name


class Program(TimeStampedModel):
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

    objects = ProgramQuerySet.as_manager()

    def __str__(self):
        return self.title

    @cached_property
    def _course_run_weeks_to_complete(self):
        return [course_run.weeks_to_complete for course_run in self.course_runs
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
    def languages(self):
        return set(course_run.language for course_run in self.course_runs if course_run.language is not None)

    @property
    def transcript_languages(self):
        languages = [course_run.transcript_languages.all() for course_run in self.course_runs]
        languages = itertools.chain.from_iterable(languages)
        return set(languages)

    @property
    def subjects(self):
        subjects = [course.subjects.all() for course in self.courses.all()]
        subjects = itertools.chain.from_iterable(subjects)
        return set(subjects)

    @property
    def seats(self):
        applicable_seat_types = set(seat_type.slug for seat_type in self.type.applicable_seat_types.all())

        for run in self.course_runs:
            for seat in run.seats.all():
                if seat.type in applicable_seat_types:
                    yield seat

    @property
    def seat_types(self):
        return set(seat.type for seat in self.seats)

    @property
    def price_ranges(self):
        currencies = defaultdict(list)
        for seat in self.seats:
            currencies[seat.currency].append(seat.price)

        price_ranges = []
        for currency, prices in currencies.items():
            price_ranges.append({
                'currency': currency.code,
                'min': min(prices),
                'max': max(prices),
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

    def save(self, *args, **kwargs):
        if waffle.switch_is_active('publish_program_to_marketing_site') and self.partner.has_marketing_site:
            # Before save, get from database the existing data if exists
            existing_program = None
            if self.id:
                existing_program = Program.objects.get(id=self.id)
            # Pass existing data to the publisher so it can decide whether we should publish
            publisher = MarketingSitePublisher(existing_program)

            with transaction.atomic():
                super(Program, self).save(*args, **kwargs)
                # Once save complete, we need to update the marketing site
                # So the marketing page for this program is automatically updated
                publisher.publish_program(self)
        else:
            super(Program, self).save(*args, **kwargs)
        self.reindex_courses()

    def reindex_courses(self):
        try:
            index = connections['default'].get_unified_index().get_index(Course)
            for course in self.courses.all():
                index.update_object(course)
                course.reindex_course_runs()
        except Exception:  # pylint: disable=broad-except
            logger.exception("An error occurred while attempting to reindex the courses"
                             "of Program with uuid: [{uuid}].".format(uuid=self.uuid))


class PersonSocialNetwork(AbstractSocialNetworkModel):
    """ Person Social Network model. """
    person = models.ForeignKey(Person, related_name='person_networks')

    class Meta(object):
        verbose_name_plural = 'Person SocialNetwork'

        unique_together = (
            ('person', 'type'),
        )


class CourseRunSocialNetwork(AbstractSocialNetworkModel):
    """ CourseRun Social Network model. """
    course_run = models.ForeignKey(CourseRun, related_name='course_run_networks')

    class Meta(object):
        verbose_name_plural = 'CourseRun SocialNetwork'

        unique_together = (
            ('course_run', 'type'),
        )


class PersonWork(AbstractValueModel):
    """ Person Works model. """
    person = models.ForeignKey(Person, related_name='person_works')
