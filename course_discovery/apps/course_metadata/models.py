import logging

from django.db import models
from django_extensions.db.models import TimeStampedModel

from course_discovery.apps.core.models import Locale, Currency

logger = logging.getLogger(__name__)


class Seat(TimeStampedModel):
    """
    Seat model.
    """
    type = models.CharField(max_length=255)
    price = models.DecimalField(decimal_places=2, max_digits=10)
    currency = models.ForeignKey(Currency)
    upgrade_deadline = models.DateTimeField()
    credit_provider_key = models.CharField(max_length=255)
    credit_hours = models.IntegerField()


class Image(TimeStampedModel):
    """
    Image model.
    """
    height = models.IntegerField()
    width = models.IntegerField()
    src = models.CharField(max_length=255)
    description = models.CharField(max_length=255)


class Video(TimeStampedModel):
    """
    Video model.
    """
    image = models.ForeignKey(Image)
    type = models.CharField(max_length=255)
    src = models.CharField(max_length=255)
    description = models.CharField(max_length=255)


class Effort(TimeStampedModel):
    """
    Effort model.
    """
    min = models.IntegerField()
    max = models.IntegerField()


class LevelType(TimeStampedModel):
    """
    LevelType model.
    """
    name = models.CharField(max_length=255)


class PacingType(TimeStampedModel):
    """
    PacingType model.
    """
    name = models.CharField(max_length=255)


class Course(TimeStampedModel):
    """
    Course model.
    """
    key = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    organizations = models.ManyToManyField('Organization', through='CourseOrganization')
    title = models.CharField(max_length=255)
    short_description = models.CharField(max_length=255)
    full_description = models.CharField(max_length=255)
    image = models.ForeignKey(Image)
    video = models.ForeignKey(Video)
    level_type = models.ForeignKey(LevelType)


class Subject(TimeStampedModel):
    """
    Subject model.
    """
    course = models.ManyToManyField(Course)
    name = models.CharField(max_length=255)


class Prerequisite(TimeStampedModel):
    """
    Prerequisite model.
    """
    course = models.ManyToManyField(Course)
    name = models.CharField(max_length=255)


class ExpectedLearningItem(TimeStampedModel):
    """
    ExpectedLearningItem model.
    """
    value = models.CharField(max_length=255)
    course = models.ForeignKey(Course)
    index = models.IntegerField()


class CourseRun(TimeStampedModel):
    """
    CourseRun model.
    """
    key = models.CharField(max_length=255)
    start = models.DateTimeField()
    end = models.DateTimeField()
    enrollment_period_start = models.DateTimeField()
    enrollment_period_end = models.DateTimeField()
    announcment = models.DateTimeField()
    title = models.CharField(max_length=255)
    short_description = models.CharField(max_length=255)
    full_description = models.CharField(max_length=255)
    image = models.ForeignKey(Image)
    video = models.ForeignKey(Video)
    locale = models.ForeignKey(Locale)
    pacing_type = models.ForeignKey(PacingType)
    effort = models.ForeignKey(Effort)
    course = models.ForeignKey(
        Course,
        db_index=True,
        default=None,
        null=False
    )
    people = models.ManyToManyField('Person', through='CourseRunPerson')
    name = models.CharField(max_length=255)


class SyllabusItem(TimeStampedModel):
    """
    SyllabusItem model.
    """
    parent = models.ForeignKey('self', blank=True, null=True, related_name='children')
    course_run = models.ForeignKey(CourseRun)
    index = models.IntegerField()
    value = models.CharField(max_length=255)


class TranscriptLocale(TimeStampedModel):
    """
    TranscriptLocale model.
    """
    locale = models.ForeignKey(Locale)
    course_run = models.ForeignKey(CourseRun)


class Organization(TimeStampedModel):
    """
    Organization model.
    """
    key = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=255)
    homepage_url = models.CharField(max_length=255)
    logo_image = models.ForeignKey(Image)


class Person(TimeStampedModel):
    """
    Person model.
    """
    key = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    bio = models.CharField(max_length=255)
    profile_image = models.ForeignKey(Image)


class CourseOrganization(TimeStampedModel):
    """
    CourseOrganization model.
    """
    course = models.ForeignKey(Course, related_name='relationship')
    organization = models.ForeignKey(Organization, related_name='relationship')
    type = models.CharField(max_length=100)


class CourseRunPerson(TimeStampedModel):
    """
    CourseRunPerson model.
    """
    course_run = models.ForeignKey(CourseRun, related_name='relationship')
    person = models.ForeignKey(Person, related_name='relationship')
    type = models.CharField(max_length=100)
    index = models.IntegerField()
