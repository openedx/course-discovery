"""
Tests for the django management command `populate_course_length`.
"""
from unittest import mock

from django.core.management import call_command
from django.test import TestCase
from pytest import mark
from testfixtures import LogCapture

from course_discovery.apps.course_metadata.models import Course
from course_discovery.apps.course_metadata.tests.factories import CourseFactory

LOGGER_NAME = 'course_discovery.apps.course_metadata.management.commands.populate_course_length'


@mark.django_db
class PopulateCourseLengthCommandTests(TestCase):
    """
    Test command `populate_course_length`.
    """

    command = 'populate_course_length'

    def setUp(self):
        super().setUp()
        self.course_a = CourseFactory()
        self.course_b = CourseFactory()

    @mock.patch(
        'course_discovery.apps.course_metadata.management.'
        'commands.populate_course_length.Command.get_query_results_from_snowflake'
    )
    def test_populate_course_length(
            self,
            mock_get_query_results,
    ):
        """
        Test that populate_course_length works correctly and saves correct data.
        """
        mock_get_query_results.return_value = [[self.course_a.uuid, 5, 'short'], [self.course_b.uuid, 12, 'medium']]
        with LogCapture(LOGGER_NAME) as log:
            call_command(self.command)
            log.check_present(
                (
                    LOGGER_NAME,
                    'INFO',
                    '[Populate Course Length]  Process started with option no_commit=True.'
                ),
                (
                    LOGGER_NAME,
                    'INFO',
                    f'''[Populate Course Length] adding 'short' as length to course with UUID {self.course_a.uuid}'''
                ),
                (
                    LOGGER_NAME,
                    'INFO',
                    f'''[Populate Course Length] adding 'medium' as length to course with UUID {self.course_b.uuid}'''
                ),
                (
                    LOGGER_NAME,
                    'INFO',
                    '[Populate Course Length] Execution completed.\n'
                    '            Courses Updated: 2\n'
                    '            Courses Update Failed: 0\n'
                    '            \n'
                    '            ',
                )
            )

            assert Course.objects.get(uuid=self.course_a.uuid).course_length == 'short'
            assert Course.objects.get(uuid=self.course_b.uuid).course_length == 'medium'

    @mock.patch(
        'course_discovery.apps.course_metadata.management.'
        'commands.populate_course_length.Command.get_query_results_from_snowflake'
    )
    def test_populate_course_length_logs_errors_for_failures(
            self,
            mock_get_query_results,
    ):
        """
        Test that populate_course_length logs correct errors and stats for failures.
        """
        dummy_uuid = '00000000-0000-0000-0000-000000000000'
        mock_get_query_results.return_value = [[self.course_a.uuid, 5, 'short'], [dummy_uuid, 12, 'medium']]
        with LogCapture(LOGGER_NAME) as log:
            call_command(self.command, '--no-commit')
            log.check_present(
                (
                    LOGGER_NAME,
                    'INFO',
                    '[Populate Course Length]  Process started with option no_commit=False.'
                ),
                (
                    LOGGER_NAME,
                    'INFO',
                    f'''[Populate Course Length] adding 'short' as length to course with UUID {self.course_a.uuid}'''
                ),
                (
                    LOGGER_NAME,
                    'INFO',
                    f'''[Populate Course Length] adding 'medium' as length to course with UUID {dummy_uuid}'''
                ),
                (
                    LOGGER_NAME,
                    'INFO',
                    f'''[Populate Course Length] No course found with UUID {dummy_uuid}'''
                ),
                (
                    LOGGER_NAME,
                    'INFO',
                    '[Populate Course Length] Execution completed.\n'
                    '            Courses Updated: 1\n'
                    '            Courses Update Failed: 1\n'
                    f'            UUIDs of courses with failures: [\'{dummy_uuid}\']\n'
                    '            ',
                )
            )
