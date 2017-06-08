import ddt
import responses
from django.core.management import CommandError, call_command
from django.test import TestCase
from testfixtures import LogCapture

from course_discovery.apps.core.tests.utils import mock_jpeg_callback
from course_discovery.apps.course_metadata.data_loaders.tests import JPEG
from course_discovery.apps.publisher.models import Course
from course_discovery.apps.publisher.tests.factories import CourseRunFactory
from course_discovery.apps.publisher.management.commands.import_course_images import logger as dataloader_logger

@ddt.ddt
class ImportCourseImagesCommandTests(TestCase):
    def setUp(self):
        super(ImportCourseImagesCommandTests, self).setUp()
        self.command_name = 'import_course_images'

    @ddt.data(
        [''],  # Raises error because both args are missing
        ['--start_id=1'],  # Raises error because 'start_id' is not provided
        ['--end_id=2'],  # Raises error because 'end_id' is not provided
    )
    def test_missing_required_arguments(self, command_args):
        """ Verify CommandError is raised when required arguments are missing """

        # If a required argument is not specified the system should raise a CommandError
        with self.assertRaises(CommandError):
            call_command(self.command_name, *command_args)

    @ddt.data(
        ['--start_id=1', '--end_id=x'],  # Raises error because 'end_id has invalid value
        ['--start_id=x', '--end_id=1']  # Raises error because both args has invalid value
    )
    def test_with_invalid_arguments(self, command_args):
        """ Verify CommandError is raised when required arguments has invalid values """

        with self.assertRaises(ValueError):
            call_command(self.command_name, *command_args)


# pylint: disable=no-member
@ddt.ddt
class ImportCourseImageTests(TestCase):
    def setUp(self):
        super(ImportCourseImageTests, self).setUp()

        self.course_run = CourseRunFactory(card_image_url='https://example.com/testing.jpg')
        self.course = self.course_run.course

        self.command_name = 'import_course_images'
        self.command_args = ['--start_id={}'.format(self.course.id), '--end_id={}'.format(self.course.id)]

    @responses.activate
    def test_course_import_image_successfully(self):
        """ Verify that course-run image successfully imported."""
        responses.add_callback(
            responses.GET,
            self.course_run.card_image_url,
            callback=mock_jpeg_callback(),
            content_type=JPEG
        )

        with LogCapture(dataloader_logger.name) as log_capture:
            call_command(self.command_name, *self.command_args)
            log_capture.check(
                (
                    log_capture.name,
                    'INFO',
                    'Successfully Import for course [{}].'.format(self.course.id)
                ),
            )

        course = Course.objects.first()
        self.assert_image(course)

    def test_course_import_without_course_run(self):
        """ Verify that course-run image successfully imported."""
        self.course_run.course = None
        self.course_run.save()
        call_command(self.command_name, *self.command_args)
        course = Course.objects.first()
        self.assert_image(course)

    # @responses.activate
    # def test_course_import_image_fail(self):
    #     """ Verify that course-run image successfully imported."""
    #     responses.add_callback(
    #         responses.GET,
    #         self.course_run.card_image_url,
    #         callback=mock_jpeg_callback(403),
    #         content_type=JPEG
    #     )
    #
    #     with LogCapture(logger.name) as log_capture:
    #         call_command(self.command_name, *self.command_args)
    #         log_capture.check(
    #             (
    #                 log_capture.name, 'WARNING',
    #                 'Loading the image for course-run [{}] failed.'.format(self.course_run.id)
    #             ),
    #         )

    def assert_image(self, course):
        """ Assert a course image loaded into DB """
        for size_key in course.image.field.variations:
            # Get different sizes specs from the model field
            # Then get the file path from the available files
            sized_image = getattr(course.image, size_key, None)
            self.assertIsNotNone(sized_image)
            if sized_image:
                path = getattr(course.image, size_key).url
                self.assertIsNotNone(path)
                self.assertIsNotNone(course.image.field.variations[size_key]['width'])
                self.assertIsNotNone(course.image.field.variations[size_key]['height'])
