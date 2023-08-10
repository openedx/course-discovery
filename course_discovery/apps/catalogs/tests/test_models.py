import ddt
from django.contrib.auth.models import ContentType, Permission
from django.test import TestCase

from course_discovery.apps.catalogs.models import Catalog
from course_discovery.apps.catalogs.tests import factories
from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.core.tests.mixins import ElasticsearchTestMixin
from course_discovery.apps.course_metadata.tests.factories import CourseFactory, CourseRunFactory


@ddt.ddt
class CatalogTests(ElasticsearchTestMixin, TestCase):
    """ Catalog model tests. """

    def setUp(self):
        super().setUp()
        self.catalog = factories.CatalogFactory(query='title:abc*')
        self.course = CourseFactory(key='a/b/c', title='ABCs of Ͳҽʂէìղց')
        self.refresh_index()

    def test_unicode(self):
        """ Validate the output of the __unicode__ method. """
        name = 'test'
        self.catalog.name = name
        self.catalog.save()

        expected = f'Catalog #{self.catalog.id}: {name}'
        self.assertEqual(str(self.catalog), expected)

    def test_courses(self):
        """ Verify the method returns a QuerySet of courses contained in the catalog. """
        self.assertEqual(list(self.catalog.courses()), [self.course])

    def test_contains(self):
        """ Verify the method returns a mapping of course IDs to booleans. """
        uncontained_course = CourseFactory(key='d/e/f', title='ABDEF')
        self.assertDictEqual(
            self.catalog.contains([self.course.key, uncontained_course.key]),
            {self.course.key: True, uncontained_course.key: False}
        )

    def test_contains_course_runs(self):
        """ Verify the method returns a mapping of course run IDs to booleans. """
        course_run = CourseRunFactory(course=self.course)
        uncontained_course_run = CourseRunFactory(title_override='ABD')
        self.assertDictEqual(
            self.catalog.contains_course_runs([course_run.key, uncontained_course_run.key]),
            {course_run.key: True, uncontained_course_run.key: False}
        )

    def test_courses_count(self):
        """ Verify the method returns the number of courses contained in the Catalog. """
        self.assertEqual(self.catalog.courses_count, 1)

        # Create a new course that should NOT be contained in the catalog, and one that should
        CourseFactory()
        CourseFactory(title='ABCDEF')
        self.assertEqual(self.catalog.courses_count, 2)

    def test_get_viewers(self):
        """ Verify the method returns a QuerySet of individuals with explicit permission to view a Catalog. """
        catalog = self.catalog
        self.assertFalse(catalog.viewers.exists())

        user = UserFactory()
        user.add_obj_perm(Catalog.VIEW_PERMISSION, catalog)
        self.assertListEqual(list(catalog.viewers), [user])

    def test_set_viewers(self):
        """ Verify the method updates the set of users with permission to view a Catalog. """
        users = UserFactory.create_batch(2)
        permission = 'catalogs.' + Catalog.VIEW_PERMISSION

        for user in users:
            self.assertFalse(user.has_perm(permission, self.catalog))

        # Verify a list of users can be added as viewers
        self.catalog.viewers = users
        for user in users:
            self.assertTrue(user.has_perm(permission, self.catalog))

        # Verify existing users, not in the list, have their access revoked.
        permitted = users[0]
        revoked = users[1]
        self.catalog.viewers = [permitted]
        self.assertTrue(permitted.has_perm(permission, self.catalog))
        self.assertFalse(revoked.has_perm(permission, self.catalog))

        # Verify all users have their access revoked when passing in an empty list
        self.catalog.viewers = []
        for user in users:
            self.assertFalse(user.has_perm(permission, self.catalog))

    @ddt.data(None, 35, 'a')
    def test_set_viewers_with_invalid_argument(self, viewers):
        """ Verify the method raises a `TypeError` if the passed value is not iterable, or is a string. """
        with self.assertRaises(TypeError) as context:
            self.catalog.viewers = viewers
        self.assertEqual(context.exception.args[0], 'Viewers must be a non-string iterable containing User objects.')

    @ddt.data('add_catalog', 'change_catalog', 'view_catalog', 'delete_catalog')
    def test_catalogs_permissions(self, perm):
        """ Validate that model has the all four permissions. """
        cont_type = ContentType.objects.get(app_label='catalogs', model='catalog')
        self.assertTrue(Permission.objects.get(content_type=cont_type, codename=perm))
