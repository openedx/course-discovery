from django.test import TestCase
from course_discovery.apps.course_metadata.management.commands import refresh_course_metadata

class RefreshCourseMetadataTests(TestCase):
    """
    Base test class for refresh_course_metadata command tests.
    """
    command = refresh_course_metadata

    def setUp(self):
        super(RefreshCourseMetadataTests, self).setUp()

    def _run_command(self, *args, **kwargs):
        """Run the management command to generate a fake cert. """
        command = self.command.Command()
        return command.handle(*args, **kwargs)

    def test_regenerating_certificate(self):
        """
        """
        self._run_command()
