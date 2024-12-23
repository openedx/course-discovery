from django.db import models
from django_extensions.db.fields import AutoSlugField
from model_utils.models import TimeStampedModel

from course_discovery.apps.course_metadata.models import Course, Program


# Create your models here.
class VerticalFilter(TimeStampedModel):
    name = models.CharField(max_length=255, unique=True)
    slug = AutoSlugField(populate_from='name', max_length=255, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = 'Vertical Filters'
        ordering = ['name']
        unique_together = ['name']

class SubVericalFilter(TimeStampedModel):
    name = models.CharField(max_length=255, unique=True)
    slug = AutoSlugField(populate_from='name', max_length=255, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    vertical_filters = models.ForeignKey(VerticalFilter, on_delete=models.CASCADE, related_name='sub_vertical_filters')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = 'Sub Vertical Filters'
        ordering = ['name']
        unique_together = ['name']

class CourseVerticalFilters(TimeStampedModel):
    course = models.OneToOneField(Course, on_delete=models.CASCADE, related_name='vertical_filters')
    vertical = models.ForeignKey(VerticalFilter, on_delete=models.CASCADE, related_name='course_vertical_filters')
    sub_vertical = models.ForeignKey(SubVericalFilter, on_delete=models.CASCADE, related_name='course_sub_vertical_filters')

    def __str__(self):
        return self.course.title

    class Meta:
        verbose_name_plural = 'Course Vertical Filters'
        ordering = ['course__title']
        unique_together = ['course']

class ProgramVerticalFilters(TimeStampedModel):
    program = models.OneToOneField(Program, on_delete=models.CASCADE, related_name='vertical_filters')
    vertical = models.ForeignKey(VerticalFilter, on_delete=models.CASCADE, related_name='program_vertical_filters')
    sub_vertical = models.ForeignKey(SubVericalFilter, on_delete=models.CASCADE, related_name='program_sub_vertical_filters')

    def __str__(self):
        return self.program.title

    class Meta:
        verbose_name_plural = 'Program Vertical Filters'
        ordering = ['program__title']
        unique_together = ['program']
