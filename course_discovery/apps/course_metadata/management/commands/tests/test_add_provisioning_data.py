"""
Unit tests for add_provisioning_data management command.
"""
import json
from unittest.mock import patch

import responses
from django.core.management import call_command
from django.test import TransactionTestCase

from course_discovery.apps.api.v1.tests.test_views.mixins import OAuth2Mixin
from course_discovery.apps.course_metadata.models import (
    Course, CourseEntitlement, CourseRun, Degree, LevelType, Person, Program, Seat, Subject
)


class AddProvisioningDataCommandTests(TransactionTestCase, OAuth2Mixin):
    """
    Test suite for add_provisioning_data management command.
    """
    def setUp(self):
        super().setUp()
        self.mock_access_token()
        responses.add(
            responses.PUT,
            'http://edx.devstack.lms:18000/api/organizations/v0/organizations/edX/',
            body=json.dumps({}),
            status=201,
        )

    @patch("course_discovery.apps.course_metadata.models.push_tracks_to_lms_for_course_run", return_value=None)
    @patch("course_discovery.apps.course_metadata.models.push_to_ecommerce_for_course_run", return_value=None)
    @patch("course_discovery.apps.api.utils.StudioAPI.create_course_run_in_studio", return_value={})
    def test_add_provisioning_data_command(self, studio_mock, ecomm_mock, lms_mock):
        """
        Verify that the command creates the relevant data in the database.
        """
        call_command('add_provisioning_data')
        assert Subject.objects.count() == 31
        assert LevelType.objects.count() == 3
        assert Person.objects.count() == 1
        assert Course.objects.count() == 2
        assert Course.everything.count() == 6
        assert CourseRun.objects.count() == 2
        assert CourseRun.everything.count() == 6
        assert Program.objects.count() == 4
        assert Degree.objects.count() == 2
        assert CourseEntitlement.everything.count() == 5
        assert CourseEntitlement.objects.count() == 2
        assert Seat.everything.count() == 12
        assert Seat.objects.count() == 5
        assert studio_mock.called
        assert lms_mock.called
        assert ecomm_mock.called
