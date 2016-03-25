import logging

from django.db import models
from django.utils.translation import ugettext_lazy as _
from django_extensions.db.models import TimeStampedModel

from course_discovery.apps.core.models import Locale, Currency

logger = logging.getLogger(__name__)


class Seat(TimeStampedModel):
    """ Seat model. """
    HONOR = 'honor'
    AUDIT = 'audit'
    VERIFIED = 'verified'
    PROFESSIONAL = 'professional'
    CREDIT = 'credit'

    SEAT_TYPE_CHOICES = (
        (HONOR, 'Honor'),
        (AUDIT, 'Audit'),
        (VERIFIED, 'Verified'),
        (PROFESSIONAL, 'Professional'),
        (CREDIT, 'Credit'),
    )
    type = models.CharField(max_length=63, choices=SEAT_TYPE_CHOICES)
    price = models.DecimalField(decimal_places=2, max_digits=10)
    currency = models.ForeignKey(Currency)
    updgrade_deadline = models.DateTimeField()
    credit_provider_key = models.CharField(max_length=255)
    credit_hours = models.IntegerField()


class Image(TimeStampedModel):
    """ Image model. """
    height = models.IntegerField()
    width = models.IntegerField()
    src = models.CharField(max_length=255)
    description = models.CharField(max_length=255)


class Video(TimeStampedModel):
    """ Video model. """
    image = models.ForeignKey(Image)
    type = models.CharField(max_length=255)
    src = models.CharField(max_length=255)
    description = models.CharField(max_length=255)


class Effort(TimeStampedModel):
    """ Effort model. """
    min = models.PositiveSmallIntegerField(
        help_text=_('The minimum bound of expected effort in hours per week. For 6-10 hours per week, the `min` is 6.')
    )
    max = models.PositiveSmallIntegerField(
        help_text=_('The maximum bound of expected effort in hours per week. For 6-10 hours per week, the `max` is 10.')
    )


class LevelType(TimeStampedModel):
    """ LevelType model. """
    name = models.CharField(max_length=255)


class PacingType(TimeStampedModel):
    """ PacingType model. """
    name = models.CharField(max_length=255)


class Subject(TimeStampedModel):
    """ Subject model. """
    name = models.CharField(max_length=255)


class Prerequisite(TimeStampedModel):
    """ Prerequisite model. """
    name = models.CharField(max_length=255)


class Course(TimeStampedModel):
    """ Course model. """
    key = models.CharField(max_length=255)
    subjects = models.ManyToManyField(Subject)
    prerequisites = models.ManyToManyField(Prerequisite)
    organizations = models.ManyToManyField('Organization', through='CourseOrganization')
    title = models.CharField(max_length=255, default=None, null=True)
    short_description = models.CharField(max_length=255, default=None, null=True)
    full_description = models.CharField(max_length=255, default=None, null=True)
    image = models.ForeignKey(Image, default=None, null=True)
    video = models.ForeignKey(Video, default=None, null=True)
    level_type = models.ForeignKey(LevelType, default=None, null=True)


class CourseRun(TimeStampedModel):
    """ CourseRun model. """
    key = models.CharField(max_length=255)
    start = models.DateTimeField(null=True)
    end = models.DateTimeField(null=True)
    enrollment_start = models.DateTimeField(null=True)
    enrollment_end = models.DateTimeField(null=True)
    announcement = models.DateTimeField(null=True)
    title = models.CharField(max_length=255, default=None, null=True)
    short_description = models.CharField(max_length=255, default=None, null=True)
    full_description = models.CharField(max_length=255, default=None, null=True)
    image = models.ForeignKey(Image, default=None, null=True)
    video = models.ForeignKey(Video, default=None, null=True)
    locale = models.ForeignKey(Locale, null=True)
    pacing_type = models.ForeignKey(PacingType, null=True)
    effort = models.ForeignKey(Effort, null=True)
    course = models.ForeignKey(Course, db_index=True, default=None, null=False)
    people = models.ManyToManyField('Person', through='CourseRunPerson')


class ExpectedLearningItem(TimeStampedModel):
    """ ExpectedLearningItem model. """
    value = models.CharField(max_length=255)
    course = models.ForeignKey(Course)
    index = models.IntegerField()


class SyllabusItem(TimeStampedModel):
    """ SyllabusItem model. """
    parent = models.ForeignKey('self', blank=True, null=True, related_name='children')
    course_run = models.ForeignKey(CourseRun)
    index = models.IntegerField()
    value = models.CharField(max_length=255)


class TranscriptLocale(TimeStampedModel):
    """ TranscriptLocale model. """
    locale = models.ForeignKey(Locale)
    course_run = models.ForeignKey(CourseRun)


class Organization(TimeStampedModel):
    """ Organization model. """
    key = models.CharField(max_length=255)
    name = models.CharField(max_length=255, null=True)
    description = models.CharField(max_length=255, null=True)
    homepage_url = models.CharField(max_length=255, null=True)
    logo_image = models.ForeignKey(Image, null=True)


class Person(TimeStampedModel):
    """ Person model. """
    key = models.CharField(max_length=255)
    name = models.CharField(max_length=255, null=True)
    title = models.CharField(max_length=255, null=True)
    bio = models.TextField(null=True)
    profile_image = models.ForeignKey(Image, null=True)
    organizations = models.ManyToManyField(Organization)


class CourseOrganization(TimeStampedModel):
    """ CourseOrganization model. """
    course = models.ForeignKey(Course, related_name='relationship')
    organization = models.ForeignKey(Organization, related_name='relationship')
    relation_type = models.CharField(max_length=100)


class CourseRunPerson(TimeStampedModel):
    """ CourseRunPerson model. """
    INSTRUCTOR = 'instructor'
    STAFF = 'staff'

    RELATION_TYPE_CHOICES = (
        (INSTRUCTOR, 'Instructor'),
        (STAFF, 'Staff'),
    )

    course_run = models.ForeignKey(CourseRun, related_name='relationship')
    person = models.ForeignKey(Person, related_name='relationship')
    relation_type = models.CharField(max_length=63, choices=RELATION_TYPE_CHOICES)
    index = models.IntegerField()
