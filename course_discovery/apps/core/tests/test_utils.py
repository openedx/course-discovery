from django.db import models
from django.test import TestCase

from course_discovery.apps.core.utils import get_all_related_field_names


class UnrelatedModel(models.Model):
    class Meta:
        app_label = 'core'
        managed = False


class RelatedModel(models.Model):
    class Meta:
        app_label = 'core'
        managed = False


class ForeignRelatedModel(models.Model):
    fk = models.ForeignKey(RelatedModel)

    class Meta:
        app_label = 'core'
        managed = False


class M2MRelatedModel(models.Model):
    m2m = models.ManyToManyField(RelatedModel)

    class Meta:
        app_label = 'core'
        managed = False


class ModelUtilTests(TestCase):
    def test_get_all_related_field_names(self):
        """ Verify the method returns the names of all relational fields for a model. """
        self.assertEqual(get_all_related_field_names(UnrelatedModel), [])
        self.assertEqual(set(get_all_related_field_names(RelatedModel)), {'foreignrelatedmodel', 'm2mrelatedmodel'})
