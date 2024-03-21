"""
Models for taxonomy related tables, these tables are placed here as opposed to inside `taxonomy-connector`
because they have direct dependency with models from course discovery.
"""
import logging

from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from model_utils.models import TimeStampedModel
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from solo.models import SingletonModel

from course_discovery.apps.course_metadata.models import Course, CourseRun, Organization

LOGGER = logging.getLogger(__name__)


class CourseRecommendation(TimeStampedModel):
    """
    Model for storing course recommendations.

    This model could easily be a `through` model in the M2M relation between Course and itself
    (i.e. through model in Course to Course ManyToMany relation.).
    """
    course = models.ForeignKey(
        Course,
        related_name='course_recommendations',
        on_delete=models.CASCADE,
        help_text=_('The original course, whose recommendation is stored here.'),
    )
    recommended_course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        help_text=_('This is the course recommended after learner completes the original course.'),
    )
    skills_intersection_ratio = models.FloatField(
        help_text=_('Ratio of number of common skills and total skill count.'),
    )
    skills_intersection_length = models.IntegerField(
        help_text=_('Count of common skills between the original course and recommended course.'),
    )
    subjects_intersection_ratio = models.FloatField(
        help_text=_('Ratio of number of common subjects and total subject count.'),
    )
    subjects_intersection_length = models.IntegerField(
        help_text=_('Count of common subjects between the original course and recommended course.'),
    )

    class Meta:
        unique_together = ('course', 'recommended_course', )
        verbose_name = _('Course Recommendation')
        verbose_name_plural = _('Course Recommendations')


class UpdateCourseRecommendationsConfig(SingletonModel):
    """
    Configuration for the update_course_recommendations management command.
    """
    all_courses = models.BooleanField(default=False, verbose_name=_('Adds recommendations for all published courses'))
    uuids = models.TextField(default='', null=False, blank=True, verbose_name=_('Course uuids'))
    num_past_days = models.IntegerField(
        default=10,
        verbose_name=_('Adds recommendations for courses created or modified in the past num days')
    )

    def __str__(self):
        return 'Configuration for the update_course_recommendations management command'


class SkillValidationConfiguration(TimeStampedModel):
    """
    Model to store the configuration for disabling skill validation for a course or organization.
    """

    course = models.ForeignKey(
        Course,
        null=True,
        blank=True,
        related_name='+',
        on_delete=models.CASCADE,
        help_text=_('The course, for which skill validation is disabled.'),
    )
    organization = models.ForeignKey(
        Organization,
        null=True,
        blank=True,
        related_name='+',
        on_delete=models.CASCADE,
        help_text=_('The organization, for which skill validation is disabled.'),
    )

    def __str__(self):
        """
        Create a human-readable string representation of the object.
        """
        message = ''

        if self.course:
            message = f'Skill validation disabled for course: {self.course.key}'
        elif self.organization:
            message = f'Skill validation disabled for organization: {self.organization.key}'

        return message

    class Meta:
        """
        Meta configuration for SkillValidationConfiguration model.
        """
        constraints = [
            models.CheckConstraint(
                check=(
                    Q(course__isnull=False) &
                    Q(organization__isnull=True)
                ) | (
                    Q(course__isnull=True) &
                    Q(organization__isnull=False)
                ),
                name='either_course_or_org',
                violation_error_message='Select either course or organization.'
            ),
            models.UniqueConstraint(fields=['course'], name="unique_course"),
            models.UniqueConstraint(fields=['organization'], name="unique_organization")
        ]

        verbose_name = 'Skill Validation Configuration'
        verbose_name_plural = 'Skill Validation Configurations'

    @staticmethod
    def is_valid_course_run_key(course_run_key):
        """
        Check if the given course run key is in valid format.

        Arguments:
            course_run_key (str): Course run key
        """
        try:
            return True, CourseKey.from_string(course_run_key)
        except InvalidKeyError:
            LOGGER.error('[TAXONOMY_SKILL_VALIDATION_CONFIGURATION] Invalid course_run key: [%s]', course_run_key)

        return False, None

    @classmethod
    def is_disabled(cls, course_run_key) -> bool:
        """
        Check if skill validation is disabled for the given course run key.

        Arguments:
            course_run_key (str): Course run key

        Returns:
            bool: True if skill validation is disabled for the given course run key.
        """
        is_valid_course_run_key, course_run_key = cls.is_valid_course_run_key(course_run_key)
        if not is_valid_course_run_key:
            return False

        course_run_org = course_run_key.org
        if cls.objects.filter(organization__key=course_run_org).exists():
            return True

        try:
            course_run = CourseRun.objects.select_related('course').get(key=course_run_key)
            course_key = course_run.course.key
        except CourseRun.DoesNotExist:
            return False

        if cls.objects.filter(course__key=course_key).exists():
            return True

        return False
