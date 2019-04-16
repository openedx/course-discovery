import datetime
import json

import ddt
import pytest
import pytz
import responses
from django.db import IntegrityError
from django.db.models.functions import Lower
from mock import mock
from rest_framework.reverse import reverse
from testfixtures import LogCapture

from course_discovery.apps.api.v1.exceptions import EditableAndQUnsupported
from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase, SerializationMixin
from course_discovery.apps.api.v1.views.courses import logger as course_logger
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.choices import CourseRunStatus, ProgramStatus
from course_discovery.apps.course_metadata.models import Course, CourseEntitlement, SeatType
from course_discovery.apps.course_metadata.tests.factories import (
    CourseEditorFactory, CourseEntitlementFactory, CourseFactory, CourseRunFactory, OrganizationFactory,
    ProgramFactory, SeatFactory, SeatTypeFactory, SubjectFactory
)
from course_discovery.apps.publisher.tests.factories import OrganizationExtensionFactory


def oauth_login(func):
    def inner(self, *args, **kwargs):
        responses.add(
            responses.POST,
            self.partner.lms_url + '/oauth2/access_token',
            body=json.dumps({'access_token': 'abcd', 'expires_in': 60}),
            status=200,
        )
        func(self, *args, **kwargs)

    return inner


@ddt.ddt
@pytest.mark.usefixtures('django_cache')
class CourseViewSetTests(SerializationMixin, APITestCase):
    def setUp(self):
        super(CourseViewSetTests, self).setUp()
        self.user = UserFactory(is_staff=True)
        self.request.user = self.user
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.course = CourseFactory(partner=self.partner, title='Fake Test', key='edX+Fake101')
        self.org = OrganizationFactory(key='edX', partner=self.partner)
        self.course.authoring_organizations.add(self.org)  # pylint: disable=no-member

    def test_get(self):
        """ Verify the endpoint returns the details for a single course. """
        url = reverse('api:v1:course-detail', kwargs={'key': self.course.key})

        with self.assertNumQueries(27):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, self.serialize_course(self.course))

    def test_get_uuid(self):
        """ Verify the endpoint returns the details for a single course with UUID. """
        url = reverse('api:v1:course-detail', kwargs={'key': self.course.uuid})

        with self.assertNumQueries(27):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, self.serialize_course(self.course))

    def test_get_exclude_deleted_programs(self):
        """ Verify the endpoint returns no deleted associated programs """
        ProgramFactory(courses=[self.course], status=ProgramStatus.Deleted)
        url = reverse('api:v1:course-detail', kwargs={'key': self.course.key})
        with self.assertNumQueries(18):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data.get('programs'), [])

    def test_get_include_deleted_programs(self):
        """
        Verify the endpoint returns associated deleted programs
        with the 'include_deleted_programs' flag set to True
        """
        ProgramFactory(courses=[self.course], status=ProgramStatus.Deleted)
        url = reverse('api:v1:course-detail', kwargs={'key': self.course.key})
        url += '?include_deleted_programs=1'
        with self.assertNumQueries(34):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response.data,
                self.serialize_course(self.course, extra_context={'include_deleted_programs': True})
            )

    def test_get_include_hidden_course_runs(self):
        """
        Verify the endpoint returns associated hidden course runs
        with the 'include_hidden_course_runs' flag set to True
        """
        CourseRunFactory(
            status=CourseRunStatus.Published,
            end=datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=10),
            enrollment_start=None,
            enrollment_end=None,
            hidden=True,
            course=self.course
        )
        url = reverse('api:v1:course-detail', kwargs={'key': self.course.key})
        url += '?include_hidden_course_runs=1'

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            self.serialize_course(self.course)
        )

    @ddt.data(1, 0)
    def test_marketable_course_runs_only(self, marketable_course_runs_only):
        """
        Verify that a client requesting marketable_course_runs_only only receives
        course runs that are published, have seats, and can still be enrolled in.
        """
        # Published course run with a seat, no enrollment start or end, and an end date in the future.
        enrollable_course_run = CourseRunFactory(
            status=CourseRunStatus.Published,
            end=datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=10),
            enrollment_start=None,
            enrollment_end=None,
            course=self.course
        )
        SeatFactory(course_run=enrollable_course_run)

        # Unpublished course run with a seat.
        unpublished_course_run = CourseRunFactory(status=CourseRunStatus.Unpublished, course=self.course)
        SeatFactory(course_run=unpublished_course_run)

        # Published course run with no seats.
        no_seats_course_run = CourseRunFactory(status=CourseRunStatus.Published, course=self.course)

        # Published course run with a seat and an end date in the past.
        closed_course_run = CourseRunFactory(
            status=CourseRunStatus.Published,
            end=datetime.datetime.now(pytz.UTC) - datetime.timedelta(days=10),
            course=self.course
        )
        SeatFactory(course_run=closed_course_run)

        url = reverse('api:v1:course-detail', kwargs={'key': self.course.key})
        url = '{}?marketable_course_runs_only={}'.format(url, marketable_course_runs_only)
        response = self.client.get(url)

        assert response.status_code == 200

        if marketable_course_runs_only:
            # Emulate prefetching behavior.
            for course_run in (unpublished_course_run, no_seats_course_run, closed_course_run):
                course_run.delete()

        assert response.data == self.serialize_course(self.course)

    @ddt.data(1, 0)
    def test_marketable_enrollable_course_runs_with_archived(self, marketable_enrollable_course_runs_with_archived):
        """ Verify the endpoint filters course runs to those that are marketable and
        enrollable, including archived course runs (with an end date in the past). """

        past = datetime.datetime.now(pytz.UTC) - datetime.timedelta(days=2)
        future = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=2)

        course_run = CourseRunFactory(enrollment_start=None, enrollment_end=future, course=self.course)
        SeatFactory(course_run=course_run)

        filtered_course_runs = [
            CourseRunFactory(enrollment_start=None, enrollment_end=None, course=self.course),
            CourseRunFactory(
                enrollment_start=past, enrollment_end=future, course=self.course
            ),
            CourseRunFactory(enrollment_start=future, course=self.course),
            CourseRunFactory(enrollment_end=past, course=self.course),
        ]

        url = reverse('api:v1:course-detail', kwargs={'key': self.course.key})
        url = '{}?marketable_enrollable_course_runs_with_archived={}'.format(
            url, marketable_enrollable_course_runs_with_archived
        )
        response = self.client.get(url)

        assert response.status_code == 200

        if marketable_enrollable_course_runs_with_archived:
            # Emulate prefetching behavior.
            for course_run in filtered_course_runs:
                course_run.delete()

        assert response.data == self.serialize_course(self.course)

    @ddt.data(1, 0)
    def test_get_include_published_course_run(self, published_course_runs_only):
        """
        Verify the endpoint returns hides unpublished programs if
        the 'published_course_runs_only' flag is set to True
        """
        CourseRunFactory(status=CourseRunStatus.Published, course=self.course)
        unpublished_course_run = CourseRunFactory(status=CourseRunStatus.Unpublished, course=self.course)

        url = reverse('api:v1:course-detail', kwargs={'key': self.course.key})
        url = '{}?published_course_runs_only={}'.format(url, published_course_runs_only)

        response = self.client.get(url)

        assert response.status_code == 200

        if published_course_runs_only:
            # Emulate prefetching behavior.
            unpublished_course_run.delete()

        assert response.data == self.serialize_course(self.course)

    def test_list(self):
        """ Verify the endpoint returns a list of all courses. """
        url = reverse('api:v1:course-list')

        with self.assertNumQueries(35):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertListEqual(
                response.data['results'],
                self.serialize_course(Course.objects.all().order_by(Lower('key')), many=True)
            )

    def test_list_query(self):
        """ Verify the endpoint returns a filtered list of courses """
        title = 'Some random title'
        courses = CourseFactory.create_batch(3, title=title)
        courses = sorted(courses, key=lambda course: course.key.lower())
        query = 'title:' + title
        url = '{root}?q={query}'.format(root=reverse('api:v1:course-list'), query=query)

        with self.assertNumQueries(51):
            response = self.client.get(url)
            self.assertListEqual(response.data['results'], self.serialize_course(courses, many=True))

    def test_list_key_filter(self):
        """ Verify the endpoint returns a list of courses filtered by the specified keys. """
        courses = CourseFactory.create_batch(3, partner=self.partner)
        courses = sorted(courses, key=lambda course: course.key.lower())
        keys = ','.join([course.key for course in courses])
        url = '{root}?keys={keys}'.format(root=reverse('api:v1:course-list'), keys=keys)

        with self.assertNumQueries(51):
            response = self.client.get(url)
            self.assertListEqual(response.data['results'], self.serialize_course(courses, many=True))

    def test_list_uuid_filter(self):
        """ Verify the endpoint returns a list of courses filtered by the specified uuid. """
        courses = CourseFactory.create_batch(3, partner=self.partner)
        courses = sorted(courses, key=lambda course: course.key.lower())
        uuids = ','.join([str(course.uuid) for course in courses])
        url = '{root}?uuids={uuids}'.format(root=reverse('api:v1:course-list'), uuids=uuids)

        with self.assertNumQueries(51):
            response = self.client.get(url)
            self.assertListEqual(response.data['results'], self.serialize_course(courses, many=True))

    def test_list_exclude_utm(self):
        """ Verify the endpoint returns marketing URLs without UTM parameters. """
        url = reverse('api:v1:course-list') + '?exclude_utm=1'

        response = self.client.get(url)
        context = {'exclude_utm': 1}
        self.assertEqual(
            response.data['results'],
            self.serialize_course([self.course], many=True, extra_context=context)
        )

    @ddt.data(
        ('get', False, False, True),
        ('options', False, False, True),
        ('post', False, False, False),
        ('post', False, True, True),
        ('post', True, False, True),
    )
    @ddt.unpack
    def test_editor_access_list_endpoint(self, method, is_staff, in_org, allowed):
        """ Verify we check editor access correctly when hitting the courses endpoint. """
        self.user.is_staff = is_staff
        self.user.save()

        if in_org:
            org_ext = OrganizationExtensionFactory(organization=self.org)
            self.user.groups.add(org_ext.group)

        response = getattr(self.client, method)(reverse('api:v1:course-list'), {'org': self.org.key}, format='json')

        if not allowed:
            self.assertEqual(response.status_code, 403)
        else:
            self.assertNotEqual(response.status_code, 403)

    @ddt.data(
        ('get', False, False, False, True),
        ('options', False, False, False, True),
        ('put', False, False, False, False),  # no access
        ('put', True, False, False, True),  # is staff
        ('patch', False, True, False, False),  # is in org
        ('patch', False, False, True, False),  # is editor but not in org
        ('put', False, True, True, True),  # editor and in org
    )
    @ddt.unpack
    def test_editor_access_detail_endpoint(self, method, is_staff, in_org, is_editor, allowed):
        """ Verify we check editor access correctly when hitting the course object endpoint. """
        self.user.is_staff = is_staff
        self.user.save()

        # Add another editor, because we have some logic that allows access anyway if a course has no valid editors.
        # That code path is checked in test_course_without_editors below.
        org_ext = OrganizationExtensionFactory(organization=self.org)
        user2 = UserFactory()
        user2.groups.add(org_ext.group)
        CourseEditorFactory(user=user2, course=self.course)

        if in_org:
            # Editors must be in the org to get editor access
            self.user.groups.add(org_ext.group)

        if is_editor:
            CourseEditorFactory(user=self.user, course=self.course)

        response = getattr(self.client, method)(reverse('api:v1:course-detail', kwargs={'key': self.course.uuid}))

        if not allowed:
            self.assertEqual(response.status_code, 404)
        else:
            # We'll probably fail because we didn't include the right data - but at least we'll have gotten in
            self.assertNotEqual(response.status_code, 404)

    def test_editable_list_gives_drafts(self):
        draft = CourseFactory(partner=self.partner, uuid=self.course.uuid, key=self.course.key, draft=True)
        draft_course_run = CourseRunFactory(
            status=CourseRunStatus.Published,
            end=datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=10),
            course=draft,
            draft=True,
        )
        self.course.draft_version = draft
        self.course.save()
        extra = CourseFactory(partner=self.partner, key=self.course.key + 'Z')  # set key so it sorts later

        response = self.client.get(reverse('api:v1:course-list') + '?editable=1')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['results'], self.serialize_course([draft, extra], many=True))
        self.assertEqual(len(response.data['results'][0]['course_runs']), 1)
        self.assertEqual(response.data['results'][0]['course_runs'][0]['uuid'], str(draft_course_run.uuid))

    def test_editable_get_gives_drafts(self):
        draft = CourseFactory(partner=self.partner, uuid=self.course.uuid, key=self.course.key, draft=True)
        self.course.draft_version = draft
        self.course.save()
        extra = CourseFactory(partner=self.partner)

        response = self.client.get(reverse('api:v1:course-detail', kwargs={'key': self.course.uuid}) + '?editable=1')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.serialize_course(draft, many=False))

        response = self.client.get(reverse('api:v1:course-detail', kwargs={'key': extra.uuid}) + '?editable=1')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.serialize_course(extra, many=False))

    def test_list_query_with_editable_raises_exception(self):
        """ Verify the endpoint raises an exception if both a q param and editable=1 are passed in """
        query = 'title:Some random title'
        url = '{root}?q={query}&editable=1'.format(root=reverse('api:v1:course-list'), query=query)

        with pytest.raises(EditableAndQUnsupported) as exc:
            self.client.get(url)

        self.assertEqual(str(exc.value), 'Specifying both editable=1 and a q parameter is not supported.')

    def test_course_without_editors(self):
        """ Verify we can modify a course with no editors if we're in its authoring org. """
        url = reverse('api:v1:course-detail', kwargs={'key': self.course.uuid})
        self.user.is_staff = False
        self.user.save()
        self.course.draft = True
        self.course.save()

        # Try without being in the organization nor an editor
        self.assertEqual(self.client.patch(url).status_code, 404)

        # Add to authoring org, and we should be let in
        org_ext = OrganizationExtensionFactory(organization=self.org)
        self.user.groups.add(org_ext.group)
        self.assertNotEqual(self.client.patch(url).status_code, 404)

        # Now add a random other user as an editor to the course, so that we will no longer be granted access.
        editor = UserFactory()
        CourseEditorFactory(user=editor, course=self.course)
        editor.groups.add(org_ext.group)
        self.assertEqual(self.client.patch(url).status_code, 404)

        # But if the editor is no longer valid (even though they exist), we're back to having access.
        editor.groups.remove(org_ext.group)
        self.assertNotEqual(self.client.patch(url).status_code, 404)

        # And finally, for a sanity check, confirm we have access when we become an editor also
        CourseEditorFactory(user=self.user, course=self.course)
        self.assertNotEqual(self.client.patch(url).status_code, 404)

    def test_delete_not_allowed(self):
        """ Verify we don't allow deleting a course from the API. """
        response = self.client.delete(reverse('api:v1:course-detail', kwargs={'key': self.course.uuid}))
        self.assertEqual(response.status_code, 405)

    def test_create_without_authentication(self):
        """ Verify authentication is required when creating a course. """
        self.client.logout()
        Course.objects.all().delete()

        url = reverse('api:v1:course-list')
        response = self.client.post(url)
        assert response.status_code == 403
        assert Course.objects.count() == 0

    def create_course(self, data=None, update=True):
        url = reverse('api:v1:course-list')
        if update:
            course_data = {
                'title': 'Course title',
                'number': 'test101',
                'org': self.org.key,
                'mode': 'audit',
            }
            course_data.update(data or {})
        else:
            course_data = data or {}
        return self.client.post(url, course_data, format='json')

    @oauth_login
    @responses.activate
    def test_create_with_authentication_verified_mode(self):
        course_data = {
            'mode': 'verified',
            'price': 100,
        }
        response = self.create_course(course_data)

        course = Course.everything.last()
        self.assertDictEqual(response.data, self.serialize_course(course))
        self.assertEqual(response.status_code, 201)
        expected_course_key = '{org}+{number}'.format(org=self.org.key, number='test101')
        self.assertEqual(course.key, expected_course_key)
        self.assertEqual(course.title, 'Course title')
        self.assertListEqual(list(course.authoring_organizations.all()), [self.org])
        self.assertEqual(1, CourseEntitlement.everything.count())  # pylint: disable=no-member

    @oauth_login
    def test_create_with_authentication_audit_mode(self):
        """
        When creating with audit mode, no entitlement should be created.
        """
        response = self.create_course()

        course = Course.everything.last()
        self.assertDictEqual(response.data, self.serialize_course(course))
        self.assertEqual(response.status_code, 201)
        expected_course_key = '{org}+{number}'.format(org=self.org.key, number='test101')
        self.assertEqual(course.key, expected_course_key)
        self.assertEqual(course.title, 'Course title')
        self.assertListEqual(list(course.authoring_organizations.all()), [self.org])
        self.assertEqual(0, CourseEntitlement.objects.count())

    @oauth_login
    def test_create_makes_draft(self):
        """ When creating a course, it should start as a draft. """
        response = self.create_course({'mode': 'verified'})
        self.assertEqual(response.status_code, 201)

        course = Course.everything.last()
        self.assertTrue(course.draft)
        self.assertTrue(course.entitlements.first().draft)

    @oauth_login
    def test_create_fails_if_official_version_exists(self):
        """ When creating a course, it should not create one if an official version already exists. """
        response = self.create_course({'number': 'Fake101'})
        self.assertEqual(response.status_code, 400)
        expected_error_message = 'Failed to set course data: A course with key {key} already exists.'
        self.assertEqual(response.data, expected_error_message.format(key=self.course.key))

    def test_create_fails_with_missing_field(self):
        response = self.create_course(
            {
                'title': 'Course title',
                'org': self.org.key,
                'mode': 'audit',
            },
            update=False
        )
        self.assertEqual(response.status_code, 400)
        expected_error_message = 'Incorrect data sent. Missing value for: [number].'
        self.assertEqual(response.data, expected_error_message)

    def test_create_fails_with_nonexistent_org(self):
        response = self.create_course({'org': 'fake org'})
        self.assertEqual(response.status_code, 400)
        expected_error_message = 'Incorrect data sent. Organization does not exist.'
        self.assertEqual(response.data, expected_error_message)

    def test_create_fails_with_nonexistent_mode(self):
        response = self.create_course({'mode': 'fake mode'})
        self.assertEqual(response.status_code, 400)
        expected_error_message = 'Incorrect data sent. Entitlement Track does not exist.'
        self.assertEqual(response.data, expected_error_message)

    @ddt.data(
        (
            {'title': 'Course title', 'number': 'test101', 'org': 'fake org', 'mode': 'fake mode'},
            'Incorrect data sent. Organization does not exist. Entitlement Track does not exist.'
        ),
        (
            {'title': 'Course title', 'org': 'edX', 'mode': 'fake mode'},
            'Incorrect data sent. Missing value for: [number]. Entitlement Track does not exist.'
        ),
        (
            {'title': 'Course title', 'org': 'fake org', 'mode': 'audit'},
            'Incorrect data sent. Missing value for: [number]. Organization does not exist.'
        ),
        (
            {'number': 'test101', 'org': 'fake org', 'mode': 'fake mode'},
            'Incorrect data sent. Missing value for: [title]. Organization does not exist. '
            'Entitlement Track does not exist.'
        ),
    )
    @ddt.unpack
    def test_create_fails_with_multiple_errors(self, course_data, expected_error_message):
        response = self.create_course(course_data, update=False)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, expected_error_message)

    def test_create_with_api_exception(self):
        with mock.patch(
            # We are using get_course_key because it is called prior to tryig to contact the
            # e-commerce service and still gives the effect of an api exception.
            'course_discovery.apps.api.v1.views.courses.CourseViewSet.get_course_key',
            side_effect=IntegrityError
        ):
            with LogCapture(course_logger.name) as log_capture:
                response = self.create_course()
                self.assertEqual(response.status_code, 400)
                log_capture.check(
                    (
                        course_logger.name,
                        'ERROR',
                        'An error occurred while setting Course data.',
                    )
                )

    def test_update_without_authentication(self):
        """ Verify authentication is required when updating a course. """
        self.client.logout()
        Course.objects.all().delete()

        url = reverse('api:v1:course-detail', kwargs={'key': self.course.uuid})
        response = self.client.patch(url)
        assert response.status_code == 403
        assert Course.objects.count() == 0

    @ddt.data('put', 'patch')
    @oauth_login
    @responses.activate
    def test_update_success(self, method):
        entitlement = CourseEntitlementFactory(course=self.course)
        url = reverse('api:v1:course-detail', kwargs={'key': self.course.uuid})
        course_data = {
            'title': 'Course title',
            'partner': self.partner.id,
            'key': self.course.key,
            'entitlements': [
                {
                    'mode': entitlement.mode.slug,
                    'price': 1000,
                    'sku': entitlement.sku,
                    'expires': entitlement.expires,
                },
            ],
            # The API is expecting the image to be base64 encoded. We are simulating that here.
            'image': 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY'
                     '42YAAAAASUVORK5CYII=',
            'video': {'src': 'https://link.to.video.for.testing/watch?t_s=5'},
        }
        response = getattr(self.client, method)(url, course_data, format='json')
        self.assertEqual(response.status_code, 200)

        course = Course.everything.get(uuid=self.course.uuid, draft=True)
        self.assertEqual(course.title, 'Course title')
        self.assertEqual(course.entitlements.first().price, 1000)
        self.assertDictEqual(response.data, self.serialize_course(course))

    @oauth_login
    @responses.activate
    def test_update_operates_on_drafts(self):
        CourseEntitlementFactory(course=self.course)
        self.assertFalse(Course.everything.filter(uuid=self.course.uuid, draft=True).exists())  # sanity check

        url = reverse('api:v1:course-detail', kwargs={'key': self.course.uuid})
        response = self.client.patch(url, {'title': 'Title'}, format='json')
        self.assertEqual(response.status_code, 200)

        course = Course.everything.get(uuid=self.course.uuid, draft=True)
        self.assertTrue(course.entitlements.first().draft)
        self.assertEqual(course.title, 'Title')

        self.course.refresh_from_db()
        self.assertFalse(self.course.draft)
        self.assertFalse(self.course.entitlements.first().draft)
        self.assertEqual(self.course.title, 'Fake Test')

    @ddt.data(
        (
            {'entitlements': [{}]},
            'Entitlements must have a mode specified.',
        ),
        (
            {'entitlements': [{'mode': 'NOPE'}]},
            'Entitlement mode NOPE not found.'
        ),
        (
            {'entitlements': [{'mode': 'mode2'}]},
            'Existing entitlement not found for mode mode2 in course Org/Course/Number.'
        ),
    )
    @ddt.unpack
    def test_update_fails_with_multiple_errors(self, course_data, expected_error_message):
        course = CourseFactory(partner=self.partner, key='Org/Course/Number')
        url = reverse('api:v1:course-detail', kwargs={'key': course.uuid})
        mode1 = SeatTypeFactory(name='Mode1')
        SeatTypeFactory(name='Mode2')
        CourseEntitlementFactory(course=course, mode=mode1, sku=None)
        response = self.client.patch(url, course_data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, expected_error_message)

    def test_update_with_api_exception(self):
        url = reverse('api:v1:course-detail', kwargs={'key': self.course.uuid})
        course_data = {
            'title': 'Course title',
            'entitlements': [
                {
                    'price': 1000,
                },
            ],
        }
        with mock.patch(
            'course_discovery.apps.api.v1.views.courses.CourseViewSet.update_entitlement',
            side_effect=IntegrityError
        ):
            with LogCapture(course_logger.name) as log_capture:
                response = self.client.patch(url, course_data, format='json')
                self.assertEqual(response.status_code, 400)
                log_capture.check(
                    (
                        course_logger.name,
                        'ERROR',
                        'An error occurred while setting Course data.',
                    )
                )

    @oauth_login
    @responses.activate
    def test_options(self):
        SubjectFactory(name='Subject1')
        CourseEntitlementFactory(course=self.course, mode=SeatType.objects.get(slug='verified'))

        url = reverse('api:v1:course-detail', kwargs={'key': self.course.uuid})
        response = self.client.options(url)
        self.assertEqual(response.status_code, 200)

        data = response.data['actions']['PUT']
        self.assertEqual(data['level_type']['choices'],
                         [{'display_name': self.course.level_type.name, 'value': self.course.level_type.name}])
        self.assertEqual(data['entitlements']['child']['children']['mode']['choices'],
                         [{'display_name': 'Audit', 'value': 'audit'},
                          {'display_name': 'Credit', 'value': 'credit'},
                          {'display_name': 'Professional', 'value': 'professional'},
                          {'display_name': 'Verified', 'value': 'verified'}])
        self.assertEqual(data['subjects']['child']['choices'],
                         [{'display_name': 'Subject1', 'value': 'subject1'}])
        self.assertFalse('choices' in data['partner'])  # we don't whitelist partner to show its choices
