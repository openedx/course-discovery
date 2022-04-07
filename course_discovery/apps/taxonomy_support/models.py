"""
Models for taxonomy related tables, these tables are placed here as opposed to inside `taxonomy-connector`
because they have direct dependency with models from course discovery.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _
from model_utils.models import TimeStampedModel
from solo.models import SingletonModel

from course_discovery.apps.course_metadata.models import Course


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

    def __str__(self):
        return f'All Courses:{self.all_courses}, UUIDs: {self.uuids}'
