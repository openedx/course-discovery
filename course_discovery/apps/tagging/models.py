from django.db import models
from django_extensions.db.fields import AutoSlugField
from model_utils.models import TimeStampedModel
from simple_history.models import HistoricalRecords

from course_discovery.apps.course_metadata.models import Course, ManageHistoryMixin


class Vertical(ManageHistoryMixin, TimeStampedModel):
    """
    Model for defining verticals used to categorize product types
    """
    name = models.CharField(max_length=255, unique=True)
    slug = AutoSlugField(populate_from='name', max_length=255, unique=True)
    is_active = models.BooleanField(default=True)
    history = HistoricalRecords()

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = 'Verticals'
        ordering = ['name']
        unique_together = ['name']

    @property
    def has_changed(self):
        if not self.pk:
            return False
        return self.has_model_changed()

    def save(self, *args, **kwargs):
        """
        Override the save method to deactivate related sub-verticals when `is_active` is set to False.
        """
        if self.pk:
            cur_instance = Vertical.objects.get(pk=self.pk)
            if cur_instance.is_active and not self.is_active:
                self.sub_verticals.update(is_active=False)

        super().save(*args, **kwargs)


class SubVertical(ManageHistoryMixin, TimeStampedModel):
    """
    Model for defining sub-verticals used to categorize product types under specific verticals.
    """
    name = models.CharField(max_length=255, unique=True)
    slug = AutoSlugField(populate_from='name', max_length=255, unique=True)
    is_active = models.BooleanField(default=True)
    verticals = models.ForeignKey(Vertical, on_delete=models.CASCADE, related_name='sub_verticals')
    history = HistoricalRecords()

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = 'Sub Verticals'
        ordering = ['name']
        unique_together = ['name']

    @property
    def has_changed(self):
        if not self.pk:
            return False
        return self.has_model_changed()

class BaseVertical(ManageHistoryMixin, TimeStampedModel):
    """
    Abstract base model for assigning vertical and sub verticals to product types.
    """
    vertical = models.ForeignKey(
        Vertical, on_delete=models.CASCADE, related_name="%(class)s_verticals"
    )
    sub_vertical = models.ForeignKey(
        SubVertical, on_delete=models.CASCADE, related_name="%(class)s_sub_verticals"
    )
    history = HistoricalRecords()

    class Meta:
        abstract = True
        ordering = ["vertical", "sub_vertical"]

    def __str__(self):
        return f'{self.get_object_title()} - {self.vertical.name} - {self.sub_vertical.name}'

    def get_object_title(self):
        """
        Returns a string representing the title of the object.
        """
        raise NotImplementedError("Subclasses must implement `get_object_title`.")

    @property
    def has_changed(self):
        if not self.pk:
            return False
        return self.has_model_changed()

class CourseVertical(BaseVertical):
    """
    Model for assigning vertical and sub verticals to courses
    """
    course = models.OneToOneField(
        Course, on_delete=models.CASCADE, related_name="verticals"
    )

    class Meta(BaseVertical.Meta):
        verbose_name_plural = "Course Verticals"
        unique_together = ["course"]

    def get_object_title(self):
        return self.course.title
