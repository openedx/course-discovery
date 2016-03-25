from django.test import TestCase

from course_discovery.apps.catalogs.tests import factories
from course_discovery.apps.core.tests.mixins import ElasticsearchTestMixin
from course_discovery.apps.course_metadata.tests.factories import CourseFactory


class CatalogTests(ElasticsearchTestMixin, TestCase):
    """ Catalog model tests. """

    def setUp(self):
        super(CatalogTests, self).setUp()
        self.catalog = factories.CatalogFactory(query='title:abc*')
        self.course = CourseFactory(key='a/b/c', title='ABCs of Ͳҽʂէìղց')
        self.refresh_index()

    def test_unicode(self):
        """ Validate the output of the __unicode__ method. """
        name = 'test'
        self.catalog.name = name
        self.catalog.save()

        expected = 'Catalog #{id}: {name}'.format(id=self.catalog.id, name=name)
        self.assertEqual(str(self.catalog), expected)

    def test_courses(self):
        """ Verify the method returns a list of courses contained in the catalog. """
        self.assertEqual(self.catalog.courses(), [self.course])

    def test_contains(self):
        """ Verify the method returns a mapping of course IDs to booleans. """
        uncontained_course = CourseFactory(key='d/e/f', title='ABDEF')
        self.assertDictEqual(
            self.catalog.contains([self.course.key, uncontained_course.key]),
            {self.course.key: True, uncontained_course.key: False}
        )
