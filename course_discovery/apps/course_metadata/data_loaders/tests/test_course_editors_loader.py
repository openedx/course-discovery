"""
Unit tests for CourseEditorsLoader.
"""
from tempfile import NamedTemporaryFile
from unittest import mock

import responses
from django.db import IntegrityError

from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase, OAuth2Mixin
from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.course_metadata.data_loaders.course_editors_loader import CourseEditorsLoader
from course_discovery.apps.course_metadata.data_loaders.tests.mixins import CSVLoaderMixin
from course_discovery.apps.course_metadata.models import CourseEditor
from course_discovery.apps.course_metadata.tests.factories import CourseFactory, OrganizationFactory
from course_discovery.apps.publisher.tests.factories import OrganizationExtensionFactory

VALID_CSV_HEADERS = ['username_or_email', 'course_key_or_uuid', 'action']


@mock.patch(
    'course_discovery.apps.course_metadata.data_loaders.configured_jwt_decode_handler',
    return_value={'preferred_username': 'test_username'}
)
class CourseEditorsLoaderTests(CSVLoaderMixin, OAuth2Mixin, APITestCase):
    """
    Test suite for CourseEditorsLoader.
    """
    def setUp(self):
        super().setUp()
        self.mock_access_token()
        self.org = OrganizationFactory()
        self.user = UserFactory(username="test_username", email="test@example.com")
        org_ext = OrganizationExtensionFactory(organization=self.org)
        self.user.groups.add(org_ext.group)
        self.course = CourseFactory(
            partner=self.partner,
            key='course-v1:test+TST101+2025',
            draft=True
        )
        self.course.authoring_organizations.add(self.org)

        self.valid_add_row = {
            'username_or_email': self.user.username,
            'course_key_or_uuid': self.course.key,
            'action': 'add',
        }

        self.valid_remove_row = {
            'username_or_email': self.user.username,
            'course_key_or_uuid': self.course.uuid,
            'action': 'remove',
        }

    def _write_csv(self, csv, lines_dict_list, headers=None):
        headers = headers or VALID_CSV_HEADERS
        csv.write((','.join(headers) + '\n').encode())

        for row in lines_dict_list:
            line = ','.join(f'"{row.get(field, "")}"' for field in headers) + '\n'
            csv.write(line.encode())

        csv.seek(0)
        return csv

    @responses.activate
    def test_ingest_add_and_remove_editor_success(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Test adding and then removing a CourseEditor in one ingestion run.
        """
        CourseEditor.objects.create(user=self.user, course=self.course)

        rows = [self.valid_add_row, self.valid_remove_row]
        with NamedTemporaryFile(mode='w+b') as csv:
            self._write_csv(csv, rows)
            loader = CourseEditorsLoader(self.partner, csv_path=csv.name)
            result = loader.ingest()

        assert result['summary']['success_count'] == 2
        assert result['summary']['failure_count'] == 0
        assert not CourseEditor.objects.filter(user=self.user, course=self.course).exists()

    @responses.activate
    def test_ingest_missing_username_and_invalid_action(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Test errors for missing username and unsupported action in two rows.
        """
        rows = [
            {'username_or_email': '', 'course_key_or_uuid': self.course.key, 'action': 'add'},
            {'username_or_email': self.user.username, 'course_key_or_uuid': self.course.key, 'action': 'invalid'},
        ]

        with NamedTemporaryFile(mode='w+b') as csv:
            self._write_csv(csv, rows)
            loader = CourseEditorsLoader(self.partner, csv_path=csv.name)
            result = loader.ingest()

        assert result['summary']['success_count'] == 0
        assert result['summary']['failure_count'] == 2

        assert result['errors']['MISSING_REQUIRED_DATA'][0] == (
            '[MISSING_REQUIRED_DATA] [Row 1] Missing required field(s): username_or_email'
        )

        assert result['errors']['UNSUPPORTED_ACTION'][0] == (
            "[UNSUPPORTED_ACTION] [Row 2] Unsupported action 'invalid' for course editor."
        )

    @responses.activate
    def test_ingest_user_not_found(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """Test failure when user is not found."""
        rows = [{
            'username_or_email': 'ghost_user',
            'course_key_or_uuid': self.course.key,
            'action': 'add',
        }]

        with NamedTemporaryFile(mode='w+b') as csv:
            self._write_csv(csv, rows)
            loader = CourseEditorsLoader(self.partner, csv_path=csv.name)
            result = loader.ingest()

        assert result['summary']['success_count'] == 0
        assert result['summary']['failure_count'] == 1
        assert result['errors']['USER_NOT_FOUND'][0] == (
            '[USER_NOT_FOUND] [Row 1] Unable to find user with identifier "ghost_user".'
        )

    @responses.activate
    def test_ingest_course_not_found(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """Test failure when course is not found."""
        unknown_course_key = 'course-v1:nonexistent+XX+0000'
        rows = [{
            'username_or_email': self.user.username,
            'course_key_or_uuid': unknown_course_key,
            'action': 'add',
        }]

        with NamedTemporaryFile(mode='w+b') as csv:
            self._write_csv(csv, rows)
            loader = CourseEditorsLoader(self.partner, csv_path=csv.name)
            result = loader.ingest()

        assert result['summary']['success_count'] == 0
        assert result['summary']['failure_count'] == 1
        assert result['errors']['COURSE_NOT_FOUND'][0] == (
            '[COURSE_NOT_FOUND] [Row 1] Unable to find course with identifier "course-v1:nonexistent+XX+0000".'
        )

    @responses.activate
    def test_ingest_user_not_in_authoring_org_and_valid_remove(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """Test mix of one failure and one success."""
        outsider = UserFactory(username='outsider')
        CourseEditor.objects.create(user=self.user, course=self.course)

        rows = [
            {'username_or_email': outsider.username, 'course_key_or_uuid': self.course.key, 'action': 'add'},
            self.valid_remove_row,
        ]

        with NamedTemporaryFile(mode='w+b') as csv:
            self._write_csv(csv, rows)
            loader = CourseEditorsLoader(self.partner, csv_path=csv.name)
            result = loader.ingest()

        assert result['summary']['success_count'] == 1
        assert result['summary']['failure_count'] == 1

        assert result['errors']['USER_ORG_MISMATCH'][0] == (
            f'[USER_ORG_MISMATCH] [Row 1] User "{outsider.username}" does not belong to any '
            f'authoring organization for course "{self.course.title}".'
        )

    @responses.activate
    @mock.patch('course_discovery.apps.course_metadata.models.CourseEditor.objects.get_or_create')
    def test_ingest_add_editor_integrity_error(self, mocked_get_or_create, jwt_decode_patch):  # pylint: disable=unused-argument
        """Test that an IntegrityError during get_or_create is handled and logged."""
        mocked_get_or_create.side_effect = IntegrityError("duplicate key")

        rows = [self.valid_add_row]
        with NamedTemporaryFile(mode='w+b') as csv:
            self._write_csv(csv, rows)
            loader = CourseEditorsLoader(self.partner, csv_path=csv.name)
            result = loader.ingest()

        assert result['summary']['success_count'] == 0
        assert result['summary']['failure_count'] == 1
        assert result['errors']['COURSE_EDITOR_ADD_ERROR'][0].startswith(
            '[COURSE_EDITOR_ADD_ERROR] [Row 1] Failed to create CourseEditor for user'
        )

    @responses.activate
    def test_ingest_remove_editor_value_error(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """Test that a ValueError during deletion is handled and logged."""
        rows = [self.valid_remove_row]
        with NamedTemporaryFile(mode='w+b') as csv:
            self._write_csv(csv, rows)
            loader = CourseEditorsLoader(self.partner, csv_path=csv.name)
            result = loader.ingest()

        assert result['summary']['success_count'] == 0
        assert result['summary']['failure_count'] == 1
        assert result['errors']['COURSE_EDITOR_REMOVE_ERROR'][0].startswith(
            '[COURSE_EDITOR_REMOVE_ERROR] [Row 1] Failed to remove CourseEditor for user'
        )
