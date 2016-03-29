import json
from unittest import skip

from django.test import TestCase

from course_discovery.apps.catalogs.tests import factories
from course_discovery.apps.core.tests.mixins import ElasticsearchTestMixin
from course_discovery.apps.course_metadata.tests.factories import CourseFactory


class CatalogTests(ElasticsearchTestMixin, TestCase):
    """ Catalog model tests. """

    def setUp(self):
        super(CatalogTests, self).setUp()
        query = {
            'query': {
                'bool': {
                    'must': [
                        {
                            'wildcard': {
                                'course.title': 'abc*'
                            }
                        }
                    ]
                }
            }
        }
        self.catalog = factories.CatalogFactory(query=json.dumps(query))
        self.course = CourseFactory(key='a/b/c', title='ABCs of Ͳҽʂէìղց')
        self.refresh_index()

    def test_unicode(self):
        """ Validate the output of the __unicode__ method. """
        name = 'test'
        self.catalog.name = name
        self.catalog.save()

        expected = 'Catalog #{id}: {name}'.format(id=self.catalog.id, name=name)
        self.assertEqual(str(self.catalog), expected)

    @skip('Skip until searching in ES is resolved')
    def test_courses(self):
        """ Verify the method returns a list of courses contained in the catalog. """
        self.assertEqual(self.catalog.courses(), [self.course])

    @skip('Skip until searching in ES is resolved')
    def test_contains(self):
        """ Verify the method returns a mapping of course IDs to booleans. """
        other_id = 'd/e/f'
        self.assertDictEqual(
            self.catalog.contains([self.course.key, other_id]),
            {self.course.key: True, other_id: False}
        )
