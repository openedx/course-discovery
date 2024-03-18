from ddt import data, ddt, unpack
from django.db import models
from django.test import TestCase

from course_discovery.apps.core.utils import (
    SearchQuerySetWrapper, delete_orphans, get_all_related_field_names, update_instance
)
from course_discovery.apps.course_metadata.models import Video
from course_discovery.apps.course_metadata.search_indexes.documents import CourseRunDocument
from course_discovery.apps.course_metadata.tests.factories import CourseRunFactory, ImageFactory, VideoFactory


class UnrelatedModel(models.Model):
    class Meta:
        app_label = 'core'
        managed = False


class RelatedModel(models.Model):
    class Meta:
        app_label = 'core'
        managed = False


class ForeignRelatedModel(models.Model):
    fk = models.ForeignKey(RelatedModel, models.CASCADE)

    class Meta:
        app_label = 'core'
        managed = False


class M2MRelatedModel(models.Model):
    m2m = models.ManyToManyField(RelatedModel)

    class Meta:
        app_label = 'core'
        managed = False


@ddt
class ModelUtilTests(TestCase):
    def test_get_all_related_field_names(self):
        """ Verify the method returns the names of all relational fields for a model. """
        assert get_all_related_field_names(UnrelatedModel) == []  # lint-amnesty, pylint: disable=use-implicit-booleaness-not-comparison
        assert set(get_all_related_field_names(RelatedModel)) == {'foreignrelatedmodel', 'm2mrelatedmodel'}

    def test_delete_orphans(self):
        """ Verify the delete_orphans method deletes orphaned instances. """
        orphan = VideoFactory()
        used = CourseRunFactory().video

        delete_orphans(Video)

        assert used.__class__.objects.filter(pk=used.pk).exists()
        assert not orphan.__class__.objects.filter(pk=orphan.pk).exists()

    def test_delete_orphans_with_exclusions(self):
        """Verify an orphan is not deleted if it is passed in as excluded"""
        orphan = VideoFactory()

        delete_orphans(Video, {orphan.pk})

        assert orphan.__class__.objects.filter(pk=orphan.pk).exists()

    @data(
        (ImageFactory, {'description': 'new image description'}),
        (VideoFactory, {'description': 'new video description'})
    )
    @unpack
    def test_update_instance(self, instance_factory, updated_data):
        """
        Verify update_instance commit changes to DB if commit flag is True.
        """
        instance = instance_factory()
        _, changed = update_instance(instance, updated_data, True)
        instance.refresh_from_db()
        assert changed
        assert instance.description == updated_data['description']

    @data(
        (ImageFactory, {'description': 'new image description'}),
        (VideoFactory, {'description': 'new video description'})
    )
    @unpack
    def test_update_instance__no_commit(self, instance_factory, updated_data):
        """
        Verify update_instance does not commit changes to DB if commit flag is False.
        """
        instance = instance_factory()
        _, changed = update_instance(instance, updated_data)
        instance.refresh_from_db()
        assert changed
        assert instance.description != updated_data['description']

    def test_update_instance__no_instance(self):
        """
        Verify the default values if no instance is provided to update_instance.
        """
        instance, changed = update_instance(None, {})
        assert instance is None
        assert not changed


class SearchQuerySetWrapperTests(TestCase):
    def setUp(self):
        super().setUp()
        title = 'Some random course'
        query = 'title:' + title

        CourseRunFactory.create_batch(3, title=title)
        self.search_queryset = CourseRunDocument().search().query('query_string', query=query)
        self.course_runs = [e.object for e in self.search_queryset]
        self.wrapper = SearchQuerySetWrapper(self.search_queryset, CourseRunFactory)

    def test_count(self):
        assert self.search_queryset.count() == self.wrapper.count()

    def test_iter(self):
        assert self.course_runs == list(self.wrapper)

    def test_getitem(self):
        assert self.course_runs[0] == self.wrapper[0]

    def test_prefetch_related_count(self):
        assert self.search_queryset.count() == self.wrapper.prefetch_related().count()

    def test_select_related_count(self):
        assert self.search_queryset.count() == self.wrapper.select_related().count()
