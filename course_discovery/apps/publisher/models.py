import logging

from django.db import models
from django.utils.translation import ugettext_lazy as _
from django_extensions.db.models import TimeStampedModel
from simple_history.models import HistoricalRecords

from course_discovery.apps.core.models import User
from course_discovery.apps.course_metadata.models import CourseRun

logger = logging.getLogger(__name__)


class Status(TimeStampedModel):
    """ Status model. """

    DRAFT = 'draft'
    REVIEW = 'review'
    PUBLISHED = 'published'

    STATUS_CHOICES = (
        (DRAFT, _('Draft')),
        (REVIEW, _('Review')),
        (PUBLISHED, _('Published')),
    )

    NON_PUBLISHED_STATUS = [DRAFT, REVIEW]

    course_run = models.OneToOneField(CourseRun, related_name='status_course_runs')
    name = models.CharField(max_length=15, choices=STATUS_CHOICES, db_index=True)

    updated_by = models.ForeignKey(User, related_name='updated_by_course_runs')
    history = HistoricalRecords()

    def __str__(self):
        return '{course_run}'.format(course_run=self.course_run.key)


class WorkflowProgram(TimeStampedModel):
    """ WorkflowProgram model."""
    XSERIES = 'xseries'
    MICRO_MASTERS = 'micromasters'

    PROGRAMS_CHOICES = (
        (XSERIES, _('XSeries')),
        (MICRO_MASTERS, _('Micro-Masters')),
    )

    type = models.CharField(max_length=15, choices=PROGRAMS_CHOICES, db_index=True, help_text=_(
        "CourseRun association with any program."))
    name = models.CharField(max_length=255, help_text=_("Name of the program."))

    def __str__(self):
        return '{type}: {name}'.format(type=self.type, name=self.name)


class WorkflowCourseRun(TimeStampedModel):
    """ WorkflowCourseRun model. It contains fields related with
    course-run."""

    XSERIES = 'xseries'
    MICRO_MASTERS = 'micromasters'

    PROGRAMS_CHOICES = (
        (XSERIES, _('XSeries')),
        (MICRO_MASTERS, _('Micro-Masters')),
    )

    course_run = models.OneToOneField(CourseRun, related_name='course_run_work_flow')
    is_re_run = models.BooleanField(default=True)

    program = models.ForeignKey(WorkflowProgram, related_name='program_work_flow')

    seo_review = models.TextField(default=None, null=True, blank=True, help_text=_(
        "SEO review on your course title and short description"))
    keywords = models.TextField(default=None, blank=True, help_text=_(
        "Please add top 10 comma separated keywords for your course content"))
    notes = models.TextField(default=None, null=True, blank=True, help_text=_(
        "Please add any additional notes or special instructions for the course About Page."))
    certificate_generation_exception = models.CharField(max_length=255, null=True, blank=True, help_text=_(
        "If you have an exception request, please note it here."))
    course_length = models.PositiveIntegerField(null=True, blank=True, help_text=_(
        "Length of course, in number of weeks"))

    target_content = models.BooleanField(default=False)
    priority = models.BooleanField(default=False)

    history = HistoricalRecords()
