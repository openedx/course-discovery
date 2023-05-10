from unittest import mock

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase

from course_discovery.apps.course_metadata.management.commands.populate_default_product_source import (
    get_products_with_no_product_source
)
from course_discovery.apps.course_metadata.models import Course, Program, Source
from course_discovery.apps.course_metadata.tests.factories import CourseFactory, ProgramFactory, SourceFactory

LOGGER_PATH = 'course_discovery.apps.course_metadata.management.commands.populate_default_product_source.logger'


class PopulateDefaultProductSourceTests(TestCase):
    """
    Test suite for populate_default_product_source management command.
    """
    default_product_source_slug = settings.DEFAULT_PRODUCT_SOURCE_SLUG

    def setUp(self):
        super().setUp()
        self.default_product_source = SourceFactory.create(slug=self.default_product_source_slug)
        self.external_test_product_source = SourceFactory.create(slug='test')

    def tearDown(self):
        super().tearDown()
        self.default_product_source.delete()
        self.external_test_product_source.delete()

    def test_populate_default_product_source___courses_with_no_existing_product_source(self):
        """
        Verify that the command updates the courses with no product_source with the default product_source.
        """
        courses = CourseFactory.create_batch(50, product_source=None, additional_metadata=None)
        with mock.patch(LOGGER_PATH) as mock_logger:
            call_command('populate_default_product_source')
            for course in courses:
                course.refresh_from_db()
                assert course.product_source.slug == self.default_product_source.slug
            assert len(courses) == Course.everything.filter(product_source=self.default_product_source).count()
            mock_logger.info.assert_has_calls([
                mock.call(f'Updated {len(courses)} courses with default product_source'),
                mock.call(
                    'Updated courses:\n' +
                    '\n'.join(f"{course.key} - {'draft' if course.draft else 'non-draft'}" for course in courses)
                )
            ])

    def test_populate_default_product_source__programs_with_no_existing_product_source(self):
        """
        Verify that the command updates the programs with no product_source with the default product_source.
        """
        programs = ProgramFactory.create_batch(50, product_source=None)
        with mock.patch(LOGGER_PATH) as mock_logger:
            call_command('populate_default_product_source', '--product_type', 'program')
            for program in programs:
                program.refresh_from_db()
                assert program.product_source.slug == self.default_product_source.slug
            assert len(programs) == Program.objects.filter(product_source=self.default_product_source).count()
            mock_logger.info.assert_has_calls([
                mock.call(f'Updated {len(programs)} programs with default product_source'),
                mock.call(
                    'Updated programs:\n' + '\n'.join(program.title for program in programs))
            ])

    def test_populate_default_product_source__with_existing_product_source(self):
        """
        Verify that the command does not update the courses with existing product_source.
        """
        test_courses = CourseFactory.create_batch(
            5, product_source=self.external_test_product_source, additional_metadata=None
        )
        with mock.patch(LOGGER_PATH) as mock_logger:
            call_command('populate_default_product_source')
            for course in test_courses:
                course.refresh_from_db()
                assert course.product_source not in (None, self.default_product_source)
                assert Course.everything.filter(product_source=self.default_product_source).count() == 0
                mock_logger.info.assert_called_once_with('Updated 0 courses with default product_source')

    def test_populate_default_product_source__programs_with_existing_product_source(self):
        """
        Verify that the command does not update the programs with existing product_source.
        """
        test_programs = ProgramFactory.create_batch(5, product_source=self.external_test_product_source)
        with mock.patch(LOGGER_PATH) as mock_logger:
            call_command('populate_default_product_source', '--product_type', 'program')
            for program in test_programs:
                program.refresh_from_db()
                assert program.product_source not in (None, self.default_product_source)
                assert Program.objects.filter(product_source=self.default_product_source).count() == 0
                mock_logger.info.assert_called_once_with('Updated 0 programs with default product_source')

    def test_invalid_product_type(self):
        """
        Verify that the command raises an exception if the product_type is not valid.
        """
        with self.assertRaises(Exception) as context:
            call_command('populate_default_product_source', '--product_type', 'test_type')
        assert 'Product Type test_type is invalid' in str(context.exception)

    def test_source_does_not_exist(self):
        """
        Verify that the command raises an exception if the default product_source does not exist.
        """
        Source.objects.filter(slug=self.default_product_source_slug).delete()
        with self.assertRaises(Exception) as context:
            call_command('populate_default_product_source')
        assert f'Default product_source {self.default_product_source_slug} does not exist' in str(context.exception)

    def test_get_products_with_no_product_source(self):
        programs = ProgramFactory.create_batch(50, product_source=None)
        courses = CourseFactory.create_batch(50, product_source=None, additional_metadata=None)
        assert len(get_products_with_no_product_source('course')) == len(courses)
        assert len(get_products_with_no_product_source('program')) == len(programs)
