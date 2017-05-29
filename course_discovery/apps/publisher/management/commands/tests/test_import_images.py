from io import BytesIO

import ddt
import responses
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from django.test import TestCase
from guardian.shortcuts import get_group_perms
from mock import Mock, patch
from PIL import Image
from testfixtures import LogCapture

from course_discovery.apps.core.tests.utils import mock_jpeg_callback
from course_discovery.apps.course_metadata.data_loaders.tests import JPEG
from course_discovery.apps.publisher.models import Course
from course_discovery.apps.publisher.tests.factories import CourseFactory, CourseRunFactory


# @ddt.ddt
# class ImportCourseImagesCommandTests(TestCase):
#     def setUp(self):
#         super(ImportCourseImagesCommandTests, self).setUp()
#         self.command_name = 'import_course_images'
#
#     @ddt.data(
#         [''],  # Raises error because both args are missing
#         ['--start_id=1'],  # Raises error because 'start_id' is not provided
#         ['--end_id=2'],  # Raises error because 'end_id' is not provided
#     )
#     def test_missing_required_arguments(self, command_args):
#         """ Verify CommandError is raised when required arguments are missing """
#
#         # If a required argument is not specified the system should raise a CommandError
#         with self.assertRaises(CommandError):
#             call_command(self.command_name, *command_args)
#
#     @ddt.data(
#         ['--start_id=1', '--end_id=x'],  # Raises error because 'end_id has invalid value
#         ['--start_id=x', '--end_id=1']  # Raises error because both args has invalid value
#     )
#     def test_with_invalid_arguments(self, command_args):
#         """ Verify CommandError is raised when required arguments has invalid values """
#
#         with self.assertRaises(ValueError):
#             call_command(self.command_name, *command_args)


# pylint: disable=no-member
@ddt.ddt
class ImportCourseImageTests(TestCase):
    def setUp(self):
        super(ImportCourseImageTests, self).setUp()
        self.course = CourseFactory()
        self.course_runs = CourseRunFactory.create_batch(3, course=self.course)
        self.course.canonical_course_run = self.course_runs[2]
        self.course.save()

        # add multiple courses.
        self.course_2 = CourseFactory()

        self.command_name = 'import_metadata_courses'
        self.command_args = ['--start_id={}'.format(self.course.id), '--end_id={}'.format(format(self.course.id))]



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
        call_command(self.command_name, *self.command_args)
        course = Course.objects.first()
        self.assert_program_banner_image_loaded(course)

    @responses.activate
    def test_course_import_image_successfully(self):
        """ Verify that course-run image successfully imported."""
        responses.add_callback(
            responses.GET,
            self.course_run.card_image_url,
            callback=mock_jpeg_callback(),
            content_type=JPEG
        )
        call_command(self.command_name, *self.command_args)
        course = Course.objects.first()
        self.assert_program_banner_image_loaded(course)


    def assert_program_banner_image_loaded(self, course):
        """ Assert a program corresponding to the specified data body has banner image loaded into DB """
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
