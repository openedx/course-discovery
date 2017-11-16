import ddt
from django.core.management import CommandError, call_command
from django.test import TestCase
from testfixtures import LogCapture

from course_discovery.apps.core.tests.helpers import make_image_file
from course_discovery.apps.course_metadata.tests.factories import CourseFactory as DiscoveryCourseFactory
from course_discovery.apps.publisher.management.commands.republish_course_images import logger as command_logger
from course_discovery.apps.publisher.tests import factories


@ddt.ddt
class RepublishCourseImageCommandTests(TestCase):
    def setUp(self):
        super(RepublishCourseImageCommandTests, self).setUp()
        self.command_name = 'republish_course_images'

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


class RepublishCourseImagesTest(TestCase):
    def setUp(self):
        super(RepublishCourseImagesTest, self).setUp()
        self.course_image = make_image_file('testimage.jpg')
        self.publisher_course = factories.CourseFactory(
            image__from_file=self.course_image
        )
        org_extension = factories.OrganizationExtensionFactory()
        organization = org_extension.organization
        self.publisher_course.organizations.add(organization)  # pylint: disable=no-member
        self.command_name = 'republish_course_images'
        self.command_args = [
            '--start_id={}'.format(self.publisher_course.id),
            '--end_id={}'.format(self.publisher_course.id)
        ]

    def _assert_images_exist(self, discovery_course):
        assert discovery_course.image.url is not None
        assert discovery_course.image.small.url is not None

    def test_command_success(self):
        discovery_course = DiscoveryCourseFactory(
            partner=self.publisher_course.partner,
            key=self.publisher_course.key
        )
        discovery_course.image.delete()
        discovery_course.save()
        call_command(self.command_name, *self.command_args)
        self._assert_images_exist(self.publisher_course.discovery_counterpart)

    def test_command_override_existing_image(self):
        DiscoveryCourseFactory(
            partner=self.publisher_course.partner,
            key=self.publisher_course.key
        )
        discovery_course = self.publisher_course.discovery_counterpart
        assert discovery_course.image.url is not None
        call_command(self.command_name, *self.command_args)
        self._assert_images_exist(discovery_course)

    def test_command_invalid_discovery_counterpart(self):
        """ Verify that if the publisher course has no discovery counterpart
            then we log the exception and move onto the next course
        """
        with LogCapture(command_logger.name) as log_capture:
            call_command(self.command_name, *self.command_args)
            log_capture.check(
                (
                    command_logger.name,
                    'WARNING',
                    'Publisher course {} has no discovery counterpart!'.format(self.publisher_course.number)
                )
            )
