from django.core.exceptions import ValidationError
from django.db import models
from django_extensions.db.fields import AutoSlugField
from model_utils.models import TimeStampedModel
from simple_history.models import HistoricalRecords

from course_discovery.apps.course_metadata.models import Course


class Vertical(TimeStampedModel):
    """
    Model for defining verticals used to categorize products
    """
    name = models.CharField(max_length=255, unique=True)
    slug = AutoSlugField(populate_from='name', max_length=255, unique=True, db_index=True)
    is_active = models.BooleanField(default=True)
    history = HistoricalRecords(excluded_fields=['slug'])

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']

    def save(self, *args, **kwargs):
        """
        Override the save method to deactivate related sub-verticals when `is_active` is set to False.
        """
        if self.pk:
            cur_instance = Vertical.objects.get(pk=self.pk)
            if cur_instance.is_active and not self.is_active:
                self.sub_verticals.update(is_active=False)

        super().save(*args, **kwargs)


class SubVertical(TimeStampedModel):
    """
    Model for defining sub-verticals used to categorize products under specific verticals.
    """
    name = models.CharField(max_length=255, unique=True)
    slug = AutoSlugField(populate_from='name', max_length=255, unique=True, db_index=True)
    is_active = models.BooleanField(default=True)
    vertical = models.ForeignKey(Vertical, on_delete=models.CASCADE, related_name='sub_verticals')
    history = HistoricalRecords(excluded_fields=['slug'])

    def __str__(self):
        return self.name


class ProductVertical(TimeStampedModel):
    """
    Abstract base model for assigning vertical and sub verticals to product types.
    """
    vertical = models.ForeignKey(
        Vertical, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_verticals"
    )
    sub_vertical = models.ForeignKey(
        SubVertical, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_sub_verticals"
    )
    history = HistoricalRecords(inherit=True)

    class Meta:
        abstract = True

    def __str__(self):
        """
        Returns a string representing the object.
        """
        vertical = self.vertical.name if self.vertical else "None"
        sub_vertical = self.sub_vertical.name if self.sub_vertical else "None"
        return f'{self.get_object_title()} - {vertical} - {sub_vertical}'

    def get_object_title(self):
        """
        Returns a string representing the title of the object.
        """
        raise NotImplementedError("Subclasses must implement `get_object_title`.")


class CourseVertical(ProductVertical):
    """
    Model for assigning vertical and sub verticals to courses
    """
    course = models.OneToOneField(
        Course, on_delete=models.CASCADE, related_name="vertical", limit_choices_to={'draft': False}
    )

    def clean(self):
        """
        Validate that the sub_vertical belongs to the selected vertical.
        Automatically set the vertical if only sub_vertical is set.
        """
        super().clean()
        if hasattr(self, 'sub_vertical') and self.sub_vertical:
            if not self.vertical:
                self.vertical = self.sub_vertical.vertical  # Auto-assign vertical if it's not set

            if self.sub_vertical.vertical and self.sub_vertical.vertical != self.vertical:
                raise ValidationError({
                    'sub_vertical': f'Sub-vertical "{self.sub_vertical.name}" does not belong to '
                                    f'vertical "{self.vertical.name}".'
                })

    def save(self, *args, **kwargs):
        """
        Call full_clean before saving to ensure validation is always run
        """
        self.full_clean()
        super().save(*args, **kwargs)

    def get_object_title(self):
        return self.course.title
