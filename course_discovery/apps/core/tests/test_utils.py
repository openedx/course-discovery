from django.db import models
from django.test import TestCase
from haystack.query import SearchQuerySet

from course_discovery.apps.core.utils import SearchQuerySetWrapper, get_all_related_field_names
from course_discovery.apps.course_metadata.models import CourseRun
from course_discovery.apps.course_metadata.tests.factories import CourseRunFactory


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


class SearchQuerySetWrapperTests(TestCase):
    def setUp(self):
        super(SearchQuerySetWrapperTests, self).setUp()
        title = 'Some random course'
        query = 'title:' + title

        CourseRunFactory.create_batch(3, title=title)
        self.search_queryset = SearchQuerySet().models(CourseRun).raw_search(query).load_all()
        self.course_runs = [e.object for e in self.search_queryset]
        self.wrapper = SearchQuerySetWrapper(self.search_queryset)

    def test_count(self):
        self.assertEqual(self.search_queryset.count(), self.wrapper.count())

    def test_iter(self):
        self.assertEqual([e for e in self.course_runs], [e for e in self.wrapper])

    def test_getitem(self):
        self.assertEqual(self.course_runs[0], self.wrapper[0])
