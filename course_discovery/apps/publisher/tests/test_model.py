from django.test import TestCase

from course_discovery.apps.publisher.tests import factories


# pylint: disable=no-member


class StatusTests(TestCase):
    """ Tests for the `Status` model. """

    def setUp(self):
        super(StatusTests, self).setUp()
        self.status = factories.StatusFactory()

    def test_str(self):
        """ Verify casting an instance to a string returns a string containing the key and type and name. """
        status = self.status
        self.assertEqual(
            str(status), '{key}: {name}'.format(
                key=status.course_run.key, name=status.name
            )
        )


class CourseRunDetailTests(TestCase):
    """ Tests for the `CourseRunDetail` model. """

    def setUp(self):
        super(CourseRunDetailTests, self).setUp()
        self.detail = factories.CourseRunDetailFactory()

    def test_str(self):
        """ Verify casting an instance to a string returns a string containing the key and type and name. """
        detail = self.detail
        self.assertEqual(
            str(detail), '{key}: {type}: {program}'.format(
                key=detail.course_run.key, type=detail.program_type, program=detail.program_name
            )
        )
