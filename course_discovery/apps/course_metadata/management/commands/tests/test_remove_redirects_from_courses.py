import ddt
from django.core.management import CommandError, call_command
from django.test import TestCase

from course_discovery.apps.core.tests.factories import PartnerFactory
from course_discovery.apps.course_metadata.models import RemoveRedirectsConfig
from course_discovery.apps.course_metadata.tests.factories import CourseFactory


@ddt.ddt
class RemoveRedirectsFromCoursesCommandTests(TestCase):
    def setUp(self):
        super().setUp()
        self.partner = PartnerFactory(marketing_site_api_password=None)
        self.course1 = CourseFactory(partner=self.partner)
        self.course2 = CourseFactory(partner=self.partner)
        self.course1.url_slug_history.create(course=self.course1, url_slug='older_course1_slug', partner=self.partner)
        self.course1.url_redirects.create(course=self.course1, partner=self.partner, value='/courses/course1')
        self.course2.url_redirects.create(course=self.course2, partner=self.partner, value='/courses/course2')

    def test_missing_arguments(self):
        with self.assertRaises(CommandError):
            call_command('remove_redirects_from_courses')

    def test_conflicting_arguments(self):
        with self.assertRaises(CommandError):
            call_command('remove_redirects_from_courses', '--args-from-database', '--remove_all')
        with self.assertRaises(CommandError):
            call_command('remove_redirects_from_courses', '--remove_all', '-url_paths', '/a/path')
        with self.assertRaises(CommandError):
            call_command('remove_redirects_from_courses', '-url_paths', '/a/path', '--args-from-database')

    @ddt.data(
        ('command_line', '--remove_all'),
        ('database', '--args-from-database'),
    )
    @ddt.unpack
    def test_remove_all(self, argument_source, argument):
        course1_active_url_slug = self.course1.active_url_slug
        course2_active_url_slug = self.course2.active_url_slug

        if argument_source == 'database':
            config = RemoveRedirectsConfig.get_solo()
            config.remove_all = True
            config.save()
        call_command('remove_redirects_from_courses', argument)

        # make sure active url_slugs remain
        self.assertEqual(self.course1.active_url_slug, course1_active_url_slug)
        self.assertEqual(self.course1.url_slug_history.count(), 1)
        self.assertEqual(self.course1.url_redirects.count(), 0)

        self.assertEqual(self.course2.active_url_slug, course2_active_url_slug)
        self.assertEqual(self.course2.url_redirects.count(), 0)

    @ddt.data(
        # test both argument sources, with and without backslash (should be backslash-insensitive)
        ('command_line', '/course/ancient_course1_slug'),
        ('database', '/course/ancient_course1_slug'),
        ('command_line', 'course/ancient_course1_slug'),
        ('database', 'course/ancient_course1_slug'),
    )
    @ddt.unpack
    def test_remove_specific_slug(self, argument_source, path):
        course1_active_url_slug = self.course1.active_url_slug
        self.course1.url_slug_history.create(course=self.course1, url_slug='ancient_course1_slug', partner=self.partner)
        if argument_source == 'database':
            config = RemoveRedirectsConfig.get_solo()
            config.url_paths = path
            config.save()
            call_command('remove_redirects_from_courses', '--args-from-database')
        else:
            call_command('remove_redirects_from_courses', '-url_paths', path)

        course1_url_slugs = list(map(lambda x: x.url_slug, self.course1.url_slug_history.all()))

        # check we removed the relevant slug
        self.assertNotIn('ancient_course1_slug', course1_url_slugs)

        # check we didn't remove anything else
        self.assertIn(course1_active_url_slug, course1_url_slugs)
        self.assertIn('older_course1_slug', course1_url_slugs)

    @ddt.data(
        # test both argument sources, with and without backslash (should be backslash-sensitive)
        ('command_line', '/courses/course1', True),
        ('database', '/courses/course1', True),
        ('command_line', 'courses/course1', False),
        ('database', 'courses/course1', False),
    )
    @ddt.unpack
    def test_remove_specific_path(self, argument_source, path, is_removed):
        self.course1.url_redirects.create(course=self.course1, partner=self.partner, value='/courses/course1/better')
        if argument_source == 'database':
            config = RemoveRedirectsConfig.get_solo()
            config.url_paths = path
            config.save()
            call_command('remove_redirects_from_courses', '--args-from-database')
        else:
            call_command('remove_redirects_from_courses', '-url_paths', path)

        course1_url_paths = list(map(lambda x: x.value, self.course1.url_redirects.all()))

        # check we removed the relevant path
        self.assertEqual('/courses/course1' not in course1_url_paths, is_removed)

        # check we didn't remove anything else
        self.assertIn('/courses/course1/better', course1_url_paths)

    def test_cannot_remove_active_url_slug(self):
        active_url_slug = self.course1.active_url_slug
        call_command('remove_redirects_from_courses', '-url_paths',
                     f'/course/{active_url_slug}')
        self.assertEqual(self.course1.active_url_slug, active_url_slug)

    def test_remove_multiple_specific_same_course(self):
        active_url_slug = self.course1.active_url_slug
        self.course1.url_redirects.create(course=self.course1, partner=self.partner, value='/courses/course1/better')
        config = RemoveRedirectsConfig.get_solo()
        config.url_paths = '/courses/course1/better /courses/course1 course/older_course1_slug'
        config.save()
        call_command('remove_redirects_from_courses', '--args-from-database')

        self.assertEqual(self.course1.active_url_slug, active_url_slug)
        self.assertEqual(self.course1.url_slug_history.count(), 1)
        self.assertEqual(self.course1.url_redirects.count(), 0)

    def test_remove_multiple_specific_different_courses(self):
        active_url_slug = self.course1.active_url_slug
        config = RemoveRedirectsConfig.get_solo()
        config.url_paths = '/courses/course2 /courses/course1 course/older_course1_slug'
        config.save()
        call_command('remove_redirects_from_courses', '--args-from-database')

        self.assertEqual(self.course1.active_url_slug, active_url_slug)
        self.assertEqual(self.course1.url_slug_history.count(), 1)
        self.assertEqual(self.course1.url_redirects.count(), 0)
        self.assertEqual(self.course2.url_redirects.count(), 0)

    def test_specific_paths_take_priority_in_database_config(self):
        self.course1.url_redirects.create(course=self.course1, partner=self.partner, value='/courses/course1/better')
        config = RemoveRedirectsConfig.get_solo()
        config.url_paths = '/courses/course1'
        config.remove_all = True
        config.save()
        call_command('remove_redirects_from_courses', '--args-from-database')
        self.assertEqual(self.course1.url_redirects.count(), 1)
