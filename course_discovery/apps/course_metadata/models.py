import datetime
import logging
from urllib.parse import urljoin
from uuid import uuid4

import pytz
from django.db import models
from django.db.models.query_utils import Q
from django.utils.translation import ugettext_lazy as _
from django_extensions.db.models import TimeStampedModel
from haystack.query import SearchQuerySet
from simple_history.models import HistoricalRecords
from sortedm2m.fields import SortedManyToManyField

from course_discovery.apps.core.models import Currency, Partner
from course_discovery.apps.course_metadata.query import CourseQuerySet
from course_discovery.apps.course_metadata.utils import clean_query
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


class LevelType(AbstractNamedModel):
    """ LevelType model. """
    pass


class Subject(AbstractNamedModel):
    """ Subject model. """
    pass


class Prerequisite(AbstractNamedModel):
    """ Prerequisite model. """
    pass


class ExpectedLearningItem(AbstractValueModel):
    """ ExpectedLearningItem model. """
    pass


class SyllabusItem(AbstractValueModel):
    """ SyllabusItem model. """
    parent = models.ForeignKey('self', blank=True, null=True, related_name='children')


class Expertise(AbstractNamedModel):
    """ Expertise model. """
    pass


class MajorWork(AbstractNamedModel):
    """ MajorWork model. """
    pass


class Organization(TimeStampedModel):
    """ Organization model. """
    key = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    homepage_url = models.URLField(max_length=255, null=True, blank=True)
    logo_image = models.ForeignKey(Image, null=True, blank=True)
    partner = models.ForeignKey(Partner, null=True, blank=False)

    history = HistoricalRecords()

    def __str__(self):
        return '{key}: {name}'.format(key=self.key, name=self.name)


class Person(TimeStampedModel):
    """ Person model. """
    key = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    title = models.CharField(max_length=255, null=True, blank=True)
    bio = models.TextField(null=True, blank=True)
    profile_image = models.ForeignKey(Image, null=True, blank=True)
    organizations = models.ManyToManyField(Organization, blank=True)
    email = models.EmailField(max_length=255, null=True, blank=True)
    username = models.CharField(max_length=255, null=True, blank=True)
    expertises = SortedManyToManyField(Expertise, blank=True, related_name='person_expertise')
    major_works = SortedManyToManyField(MajorWork, blank=True, related_name='person_works')

    history = HistoricalRecords()

    def __str__(self):
        return '{key}: {name}'.format(key=self.key, name=self.name)

    class Meta(object):
        verbose_name_plural = 'People'


class Course(TimeStampedModel):
    """ Course model. """
    key = models.CharField(max_length=255, db_index=True, unique=True)
    title = models.CharField(max_length=255, default=None, null=True, blank=True)
    short_description = models.CharField(max_length=255, default=None, null=True, blank=True)
    full_description = models.TextField(default=None, null=True, blank=True)
    organizations = models.ManyToManyField('Organization', through='CourseOrganization', blank=True)
    subjects = models.ManyToManyField(Subject, blank=True)
    prerequisites = models.ManyToManyField(Prerequisite, blank=True)
    level_type = models.ForeignKey(LevelType, default=None, null=True, blank=True)
    expected_learning_items = SortedManyToManyField(ExpectedLearningItem, blank=True)
    image = models.ForeignKey(Image, default=None, null=True, blank=True)
    video = models.ForeignKey(Video, default=None, null=True, blank=True)
    marketing_url = models.URLField(max_length=255, null=True, blank=True)
    learner_testimonial = models.CharField(
        max_length=50, null=True, blank=True, help_text=_(
            "A quote from a learner in the course, demonstrating the value of taking the course"
        )
    )

    number = models.CharField(
        max_length=50, null=True, blank=True, help_text=_(
            "Course number format e.g CS002x, BIO1.1x, BIO1.2x"
        )
    )

    history = HistoricalRecords()
    objects = CourseQuerySet.as_manager()
    partner = models.ForeignKey(Partner, null=True, blank=False)

    @property
    def owners(self):
        return self.organizations.filter(courseorganization__relation_type=CourseOrganization.OWNER)

    @property
    def sponsors(self):
        return self.organizations.filter(courseorganization__relation_type=CourseOrganization.SPONSOR)

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

    def __str__(self):
        return '{key}: {title}'.format(key=self.key, title=self.title)


class CourseRun(TimeStampedModel):
    """ CourseRun model. """
    SELF_PACED = 'self_paced'
    INSTRUCTOR_PACED = 'instructor_paced'

    PACING_CHOICES = (
        # Translators: Self-paced refers to course runs that operate on the student's schedule.
        (SELF_PACED, _('Self-paced')),

        # Translators: Instructor-paced refers to course runs that operate on a schedule set by the instructor,
        # similar to a normal university course.
        (INSTRUCTOR_PACED, _('Instructor-paced')),
    )

    course = models.ForeignKey(Course, related_name='course_runs')
    key = models.CharField(max_length=255, unique=True)
    title_override = models.CharField(
        max_length=255, default=None, null=True, blank=True,
        help_text=_(
            "Title specific for this run of a course. Leave this value blank to default to the parent course's title."))
    start = models.DateTimeField(null=True, blank=True)
    end = models.DateTimeField(null=True, blank=True)
    enrollment_start = models.DateTimeField(null=True, blank=True)
    enrollment_end = models.DateTimeField(null=True, blank=True)
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
    instructors = SortedManyToManyField(Person, blank=True, related_name='courses_instructed')
    staff = SortedManyToManyField(Person, blank=True, related_name='courses_staffed')
    min_effort = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text=_('Estimated minimum number of hours per week needed to complete a course run.'))
    max_effort = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text=_('Estimated maximum number of hours per week needed to complete a course run.'))
    language = models.ForeignKey(LanguageTag, null=True, blank=True)
    transcript_languages = models.ManyToManyField(LanguageTag, blank=True, related_name='transcript_courses')
    pacing_type = models.CharField(max_length=255, choices=PACING_CHOICES, db_index=True, null=True, blank=True)
    syllabus = models.ForeignKey(SyllabusItem, default=None, null=True, blank=True)
    image = models.ForeignKey(Image, default=None, null=True, blank=True)
    video = models.ForeignKey(Video, default=None, null=True, blank=True)
    marketing_url = models.URLField(max_length=255, null=True, blank=True)

    history = HistoricalRecords()

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
    def organizations(self):
        return self.course.organizations

    @property
    def seat_types(self):
        return list(self.seats.values_list('type', flat=True))

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

        logger.warning('Unable to determine type for course run [%s]. Seat types are [%s]', self.key, seat_types)
        return None

    @property
    def image_url(self):
        if self.image:
            return self.image.src

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


class Seat(TimeStampedModel):
    """ Seat model. """
    HONOR = 'honor'
    AUDIT = 'audit'
    VERIFIED = 'verified'
    PROFESSIONAL = 'professional'
    CREDIT = 'credit'

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
    type = models.CharField(max_length=63, choices=SEAT_TYPE_CHOICES)
    price = models.DecimalField(**PRICE_FIELD_CONFIG)
    currency = models.ForeignKey(Currency)
    upgrade_deadline = models.DateTimeField(null=True, blank=True)
    credit_provider = models.CharField(max_length=255, null=True, blank=True)
    credit_hours = models.IntegerField(null=True, blank=True)

    history = HistoricalRecords()

    class Meta(object):
        unique_together = (
            ('course_run', 'type', 'currency', 'credit_provider')
        )


class CourseOrganization(TimeStampedModel):
    """ CourseOrganization model. """
    OWNER = 'owner'
    SPONSOR = 'sponsor'

    RELATION_TYPE_CHOICES = (
        (OWNER, _('Owner')),
        (SPONSOR, _('Sponsor')),
    )

    course = models.ForeignKey(Course)
    organization = models.ForeignKey(Organization)
    relation_type = models.CharField(max_length=63, choices=RELATION_TYPE_CHOICES)

    class Meta(object):
        index_together = (
            ('course', 'relation_type'),
        )
        unique_together = (
            ('course', 'organization', 'relation_type'),
        )


class Program(TimeStampedModel):
    """
    Representation of a Program.
    """
    uuid = models.UUIDField(
        blank=True,
        default=uuid4,
        editable=False,
        unique=True,
        verbose_name=_('UUID')
    )

    title = models.CharField(
        help_text=_('The user-facing display title for this Program.'),
        max_length=255,
        unique=True,
    )

    subtitle = models.CharField(
        help_text=_('A brief, descriptive subtitle for the Program.'),
        max_length=255,
        blank=True,
    )

    category = models.CharField(
        help_text=_('The category / type of Program.'),
        max_length=32,
    )

    status = models.CharField(
        help_text=_('The lifecycle status of this Program.'),
        max_length=24,
    )

    marketing_slug = models.CharField(
        help_text=_('Slug used to generate links to the marketing site'),
        blank=True,
        max_length=255,
        db_index=True
    )

    image = models.ForeignKey(Image, default=None, null=True, blank=True)

    organizations = models.ManyToManyField(Organization, blank=True)

    partner = models.ForeignKey(Partner, null=True, blank=False)

    def __str__(self):
        return self.title

    @property
    def marketing_url(self):
        if self.marketing_slug:
            path = '{category}/{slug}'.format(category=self.category, slug=self.marketing_slug)
            return urljoin(self.partner.marketing_site_url_root, path)

        return None

    @property
    def image_url(self):
        if self.image:
            return self.image.src

        return None


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
