from django.db import models
from django_extensions.db.fields import AutoSlugField
from model_utils.models import TimeStampedModel

from course_discovery.apps.course_metadata.models import Course, Program, Degree


class VerticalFilter(TimeStampedModel):
    """
    This model is used to store the vertical mapping for the courses.
    """
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
    """
    This model is used to store the sub vertical mapping for the courses.
    """
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
    """
    Model used to assign vertical and sub vertical filters to course.
    """
    course = models.OneToOneField(Course, on_delete=models.CASCADE, related_name='vertical_filters')
    vertical = models.ForeignKey(VerticalFilter, on_delete=models.CASCADE, related_name='course_vertical_filters')
    sub_vertical = models.ForeignKey(
        SubVericalFilter,
        on_delete=models.CASCADE,
        related_name="course_sub_vertical_filters",
    )

    def __str__(self):
        return f'{self.course.title} - {self.vertical.name} - {self.sub_vertical.name}'

    class Meta:
        verbose_name_plural = 'Course Vertical Filters'
        ordering = ['course__title']
        unique_together = ['course']


class ProgramVericalFilters(TimeStampedModel):
    """
    Model used to assign verticals to program.
    """
    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name='program_verticals')
    vertical = models.ForeignKey(VerticalFilter, on_delete=models.CASCADE, related_name='program_vertical_filters')
    sub_vertical = models.ForeignKey(
        SubVericalFilter,
        on_delete=models.CASCADE,
        related_name='program_sub_vertical_filters',
    )

    def __str__(self):
        return f'{self.program.title} - {self.vertical.name} - {self.sub_vertical.name}'

    class Meta:
        verbose_name_plural = 'Program Verticals'
        ordering = ['program__title']
        unique_together = ['program', 'vertical']

class VerticalFilterTags(TimeStampedModel):
    """
    Model used to assign vertical and sub-vertical filters to Course, Program, or Degree.
    """
    CONTENT_TYPE_CHOICES = [
        ('course', 'Course'),
        ('program', 'Program'),
        ('degree', 'Degree'),
    ]

    content_type = models.CharField(max_length=10, choices=CONTENT_TYPE_CHOICES)
    object_id = models.UUIDField()

    vertical = models.ForeignKey(VerticalFilter, on_delete=models.CASCADE, related_name='vertical_filters')
    sub_vertical = models.ForeignKey(
        SubVericalFilter,
        on_delete=models.CASCADE,
        related_name='sub_vertical_filters',
    )

    def __str__(self):
        return f'{self.get_object_title()} - {self.vertical.name} - {self.sub_vertical.name}'

    def get_object_title(self):
        """
        Retrieve the title of the related object based on its type.
        """
        if self.content_type == 'course':
            return Course.objects.filter(uuid=self.object_id).first().title
        elif self.content_type == 'program':
            return Program.objects.filter(uuid=self.object_id).first().title
        elif self.content_type == 'degree':
            return Degree.objects.filter(uuid=self.object_id).first().title
        else:
            return None 

    class Meta:
        verbose_name_plural = 'Vertical Filter Tags'
        ordering = ['content_type', 'object_id']
        unique_together = ['content_type', 'object_id', 'vertical']
