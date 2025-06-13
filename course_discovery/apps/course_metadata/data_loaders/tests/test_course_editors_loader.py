"""
Unit tests for course_editors_loader.
"""
from tempfile import NamedTemporaryFile

import responses
from unittest import mock

from course_discovery.apps.api.v1.tests.test_views.mixins import OAuth2Mixin, APITestCase
from course_discovery.apps.course_metadata.data_loaders.course_editors_loader import CourseEditorsLoader
from course_discovery.apps.course_metadata.data_loaders.tests.mixins import CSVLoaderMixin
from course_discovery.apps.course_metadata.models import CourseEditor
from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.course_metadata.tests.factories import CourseFactory, OrganizationFactory
from course_discovery.apps.publisher.tests.factories import OrganizationExtensionFactory

VALID_CSV_HEADERS = ['username_or_email', 'course_key_or_uuid', 'action']


@mock.patch(
    'course_discovery.apps.course_metadata.data_loaders.configured_jwt_decode_handler',
    return_value={'preferred_username': 'test_username'}
)
class CourseEditorsLoaderTests(CSVLoaderMixin, OAuth2Mixin, APITestCase):
    """
    Test Suite for CourseEditorsLoader.
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

    def _write_csv(self, csv, lines_dict_list, headers=None):
        """
        Override: Write CourseEditor data to CSV using snake_case headers.
        """
        if headers is None:
            headers = VALID_CSV_HEADERS

        header_line = ','.join(headers) + '\n'
        csv.write(header_line.encode())

        for row in lines_dict_list:
            line = ','.join(f'"{row.get(field, "")}"' for field in headers) + '\n'
            csv.write(line.encode())

        csv.seek(0)
        return csv

    @responses.activate
    def test_ingest_add_editor_success(self, jwt_decode_patch):
        """Test successfully adding a CourseEditor entry."""
        with NamedTemporaryFile(mode='w+b') as csv:
            self._write_csv(csv, [{
                'username_or_email': self.user.username,
                'course_key_or_uuid': self.course.key,
                'action': 'add',
            }])
            loader = CourseEditorsLoader(self.partner, csv_path=csv.name)
            result = loader.ingest()

        self.assertEqual(result['summary']['success_count'], 1)
        self.assertEqual(result['summary']['failure_count'], 0)
        self.assertTrue(CourseEditor.objects.filter(user=self.user, course=self.course).exists())

    @responses.activate
    def test_ingest_remove_editor_success(self, jwt_decode_patch):
        """Test removing an existing CourseEditor entry."""
        CourseEditor.objects.create(user=self.user, course=self.course)

        with NamedTemporaryFile(mode='w+b') as csv:
            self._write_csv(csv, [{
                'username_or_email': self.user.username,
                'course_key_or_uuid': self.course.key,
                'action': 'remove',
            }])
            loader = CourseEditorsLoader(self.partner, csv_path=csv.name)
            result = loader.ingest()

        self.assertEqual(result['summary']['success_count'], 1)
        self.assertEqual(result['summary']['failure_count'], 0)
        self.assertFalse(CourseEditor.objects.filter(user=self.user, course=self.course).exists())

    @responses.activate
    def test_ingest_missing_fields(self, jwt_decode_patch):
        """Test failure due to missing required fields."""
        with NamedTemporaryFile(mode='w+b') as csv:
            self._write_csv(csv, [{
                'username_or_email': '',
                'course_key_or_uuid': self.course.key,
                'action': 'add',
            }])
            loader = CourseEditorsLoader(self.partner, csv_path=csv.name)
            result = loader.ingest()

        self.assertEqual(result['summary']['success_count'], 0)
        self.assertEqual(result['summary']['failure_count'], 1)
        self.assertIn('username_or_email', result['errors']['MISSING_REQUIRED_DATA'][0])

    @responses.activate
    def test_ingest_user_not_found(self, jwt_decode_patch):
        """Test failure when user is not found."""
        with NamedTemporaryFile(mode='w+b') as csv:
            self._write_csv(csv, [{
                'username_or_email': 'nonexistent',
                'course_key_or_uuid': self.course.key,
                'action': 'add',
            }])
            loader = CourseEditorsLoader(self.partner, csv_path=csv.name)
            result = loader.ingest()

        self.assertEqual(result['summary']['success_count'], 0)
        self.assertEqual(result['summary']['failure_count'], 1)
        self.assertIn('USER_NOT_FOUND', result['errors'])

    @responses.activate
    def test_ingest_course_not_found(self, jwt_decode_patch):
        """Test failure when course is not found."""
        with NamedTemporaryFile(mode='w+b') as csv:
            self._write_csv(csv, [{
                'username_or_email': self.user.username,
                'course_key_or_uuid': 'course-v1:nonexistent+XX+0000',
                'action': 'add',
            }])
            loader = CourseEditorsLoader(self.partner, csv_path=csv.name)
            result = loader.ingest()

        self.assertEqual(result['summary']['success_count'], 0)
        self.assertEqual(result['summary']['failure_count'], 1)
        self.assertIn('COURSE_NOT_FOUND', result['errors'])

    @responses.activate
    def test_ingest_user_not_in_authoring_org(self, jwt_decode_patch):
        """Test failure when user doesn't belong to course org."""
        new_user = UserFactory(username="outsider")

        with NamedTemporaryFile(mode='w+b') as csv:
            self._write_csv(csv, [{
                'username_or_email': new_user.username,
                'course_key_or_uuid': self.course.key,
                'action': 'add',
            }])
            loader = CourseEditorsLoader(self.partner, csv_path=csv.name)
            result = loader.ingest()

        self.assertEqual(result['summary']['success_count'], 0)
        self.assertEqual(result['summary']['failure_count'], 1)
        self.assertIn('USER_DOES_NOT_BELONG_TO_ORG', result['errors'])

    @responses.activate
    def test_ingest_invalid_action(self, jwt_decode_patch):
        """Test failure on unsupported action."""
        with NamedTemporaryFile(mode='w+b') as csv:
            self._write_csv(csv, [{
                'username_or_email': self.user.username,
                'course_key_or_uuid': self.course.key,
                'action': 'update',
            }])
            loader = CourseEditorsLoader(self.partner, csv_path=csv.name)
            result = loader.ingest()

        self.assertEqual(result['summary']['success_count'], 0)
        self.assertEqual(result['summary']['failure_count'], 1)
        self.assertIn('Unsupported action', result['errors']['MISSING_REQUIRED_DATA'][0])
