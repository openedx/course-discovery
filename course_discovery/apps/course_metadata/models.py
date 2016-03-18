import logging

from django.db import models
from django_extensions.db.models import TimeStampedModel

logger = logging.getLogger(__name__)


class Course(TimeStampedModel):
    """
    Course model.
    """
    key  = models.CharField(max_length=255)
    name = models.CharField(max_length=255)


class CourseRun(TimeStampedModel):
    """
    CourseRun model.
    """
    key    = models.CharField(max_length=255)
    course = models.ForeignKey(
        Course,
        db_index=True,
        default=None,
        null=False
    )


class Organization(TimeStampedModel):
    """
    Organization model.
    """
    key = models.CharField(max_length=255)


class Person(TimeStampedModel):
    """
    Person model.
    """
    key = models.CharField(max_length=255)
