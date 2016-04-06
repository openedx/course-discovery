import datetime
import logging

import pytz
from django.db import models
from django.utils.translation import ugettext_lazy as _
from django_extensions.db.models import TimeStampedModel
from simple_history.models import HistoricalRecords
from sortedm2m.fields import SortedManyToManyField

from course_discovery.apps.core.models import Currency
from course_discovery.apps.course_metadata.query import CourseQuerySet
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


class Organization(TimeStampedModel):
    """ Organization model. """
    key = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    homepage_url = models.URLField(max_length=255, null=True, blank=True)
    logo_image = models.ForeignKey(Image, null=True, blank=True)

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

    history = HistoricalRecords()
    objects = CourseQuerySet.as_manager()

    @property
    def owners(self):
        return self.organizations.filter(courseorganization__relation_type=CourseOrganization.OWNER)

    @property
    def sponsors(self):
        return self.organizations.filter(courseorganization__relation_type=CourseOrganization.SPONSOR)

    @property
    def active_course_runs(self):
        """ Returns course runs currently open for enrollment, or opening in the future.

        Returns:
            QuerySet
        """
        return self.course_runs.filter(enrollment_end__gt=datetime.datetime.now(pytz.UTC))

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
