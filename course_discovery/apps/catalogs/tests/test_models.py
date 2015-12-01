from django.test import TestCase

from course_discovery.apps.catalogs.tests import factories


class CatalogTests(TestCase):
    """ Catalog model tests. """

    def setUp(self):
        super(CatalogTests, self).setUp()
        self.catalog = factories.CatalogFactory()

    def test_unicode(self):
        """ Validate the output of the __unicode__ method. """
        name = 'test'
        self.catalog.name = name
        self.catalog.save()

        expected = 'Catalog #{id}: {name}'.format(id=self.catalog.id, name=name)
        self.assertEqual(str(self.catalog), expected)

    def test_courses(self):
        """ Verify the method returns a list of courses contained in the catalog. """
        # TODO Setup/mock Elasticsearch
        # TODO Set catalog query
        # TODO Validate value of catalog.courses()
        self.assertListEqual(self.catalog.courses(), [])

    def test_contains(self):
        """ Verify the method returns a mapping of course IDs to booleans. """
        # TODO Setup/mock Elasticsearch
        # TODO Set catalog query
        # TODO Validate value of catalog.contains()
        self.assertDictEqual(self.catalog.contains([]), {})
