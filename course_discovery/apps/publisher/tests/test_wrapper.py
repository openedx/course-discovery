# pylint: disable=no-member
from datetime import datetime, timedelta
from unittest import mock

import ddt
from django.test import TestCase

from course_discovery.apps.course_metadata.choices import CourseRunPacing
from course_discovery.apps.course_metadata.tests.factories import (
    OrganizationFactory, PersonFactory, PersonSocialNetworkFactory, PositionFactory
)
from course_discovery.apps.publisher.choices import CourseRunStateChoices, PublisherUserRole
from course_discovery.apps.publisher.models import Seat
from course_discovery.apps.publisher.tests import factories
from course_discovery.apps.publisher.wrappers import CourseRunWrapper


@ddt.ddt
class CourseRunWrapperTests(TestCase):
    """ Tests for the publisher `BaseWrapper` model. """

    def setUp(self):
        super(CourseRunWrapperTests, self).setUp()
        self.course_run = factories.CourseRunFactory()
        self.course = self.course_run.course

        self.wrapped_course_run = CourseRunWrapper(self.course_run)

    def test_title(self):
        """ Verify that the wrapper can override course_run title. """
        self.assertEqual(self.wrapped_course_run.title, self.course_run.course.title)

    def test_model_attr(self):
        """ Verify that the wrapper passes through object values not defined on wrapper. """
        self.assertEqual(self.wrapped_course_run.lms_course_id, self.course_run.lms_course_id)

    def test_callable(self):
        mock_callable = mock.Mock(return_value='callable_value')
        mock_obj = mock.MagicMock(callable_attr=mock_callable)
        wrapper = CourseRunWrapper(mock_obj)

        self.assertEqual(wrapper.callable_attr(), 'callable_value')

    def _generate_seats(self, modes):
        for mode in modes:
            factories.SeatFactory(type=mode, course_run=self.course_run)

    def test_is_authored_in_studio(self):
        """ Verify that the wrapper return the is_authored_in_studio. """
        self.assertFalse(self.wrapped_course_run.is_authored_in_studio)
        self.course_run.lms_course_id = 'test/course/id'
        self.course_run.save()
        self.assertTrue(self.wrapped_course_run.is_authored_in_studio)

    def test_mdc_submission_due_date(self):
        """ Verify that the wrapper return the mdc_submission_due_date. """
        current_date = datetime.today()
        expected_date = current_date - timedelta(days=10)
        self.course_run.start = current_date
        self.course_run.save()
        self.assertEqual(self.wrapped_course_run.mdc_submission_due_date, expected_date)

    def _change_state_and_owner(self, course_run_state):
        """
        Change course run state to review and ownership to project coordinator.
        """
        course_run_state.name = CourseRunStateChoices.Review
        course_run_state.change_owner_role(PublisherUserRole.ProjectCoordinator)
