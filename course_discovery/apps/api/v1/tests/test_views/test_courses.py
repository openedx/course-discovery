import datetime
import json

import ddt
import pytest
import pytz
import responses
from django.conf import settings
from django.db import IntegrityError
from django.db.models.functions import Lower
from mock import mock
from rest_framework.reverse import reverse
from testfixtures import LogCapture

from course_discovery.apps.api.v1.exceptions import EditableAndQUnsupported
from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase, FuzzyInt, OAuth2Mixin, SerializationMixin
from course_discovery.apps.api.v1.views.courses import logger as course_logger
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.choices import CourseRunStatus, ProgramStatus
from course_discovery.apps.course_metadata.models import (
    Course, CourseEditor, CourseEntitlement, CourseRun, Seat, SeatType
)
from course_discovery.apps.course_metadata.tests.factories import (
    CourseEditorFactory, CourseEntitlementFactory, CourseFactory, CourseRunFactory, OrganizationFactory, ProgramFactory,
    SeatFactory, SeatTypeFactory, SubjectFactory
)
from course_discovery.apps.course_metadata.utils import ensure_draft_world
from course_discovery.apps.publisher.tests.factories import OrganizationExtensionFactory


@ddt.ddt
@pytest.mark.usefixtures('django_cache')
class CourseViewSetTests(OAuth2Mixin, SerializationMixin, APITestCase):
    def setUp(self):
        super(CourseViewSetTests, self).setUp()
        self.user = UserFactory(is_staff=True)
        self.request.user = self.user
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.course = CourseFactory(partner=self.partner, title='Fake Test', key='edX+Fake101')
        self.org = OrganizationFactory(key='edX', partner=self.partner)
        self.course.authoring_organizations.add(self.org)  # pylint: disable=no-member

    def mock_ecommerce_publication(self):
        url = '{root}publication/'.format(root=self.course.partner.ecommerce_api_url)
        responses.add(responses.POST, url, json={}, status=200)

    def test_get(self):
        """ Verify the endpoint returns the details for a single course. """
        url = reverse('api:v1:course-detail', kwargs={'key': self.course.key})

        with self.assertNumQueries(45):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, self.serialize_course(self.course))

    def test_get_uuid(self):
        """ Verify the endpoint returns the details for a single course with UUID. """
        url = reverse('api:v1:course-detail', kwargs={'key': self.course.uuid})

        with self.assertNumQueries(FuzzyInt(43, 3)):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, self.serialize_course(self.course))

    def test_get_exclude_deleted_programs(self):
        """ Verify the endpoint returns no deleted associated programs """
        ProgramFactory(courses=[self.course], status=ProgramStatus.Deleted)
        url = reverse('api:v1:course-detail', kwargs={'key': self.course.key})
        with self.assertNumQueries(31):
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
        with self.assertNumQueries(51):
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

        with self.assertNumQueries(38):
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

        with self.assertNumQueries(FuzzyInt(55, 2)):
            response = self.client.get(url)
            self.assertListEqual(response.data['results'], self.serialize_course(courses, many=True))

    def test_list_key_filter(self):
        """ Verify the endpoint returns a list of courses filtered by the specified keys. """
        courses = CourseFactory.create_batch(3, partner=self.partner)
        courses = sorted(courses, key=lambda course: course.key.lower())
        keys = ','.join([course.key for course in courses])
        url = '{root}?keys={keys}'.format(root=reverse('api:v1:course-list'), keys=keys)

        with self.assertNumQueries(57):
            response = self.client.get(url)
            self.assertListEqual(response.data['results'], self.serialize_course(courses, many=True))

    def test_list_uuid_filter(self):
        """ Verify the endpoint returns a list of courses filtered by the specified uuid. """
        courses = CourseFactory.create_batch(3, partner=self.partner)
        courses = sorted(courses, key=lambda course: course.key.lower())
        uuids = ','.join([str(course.uuid) for course in courses])
        url = '{root}?uuids={uuids}'.format(root=reverse('api:v1:course-list'), uuids=uuids)

        with self.assertNumQueries(56):
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

    def test_list_pubq_by_title(self):
        """ Verify the endpoint returns a list of courses filtered by title when specified with pubq and editable """
        url = reverse('api:v1:course-list') + '?editable=1&pubq=ThisIsASpecificTestString'

        self.course.title = 'ThisIsASpecificTestStringTitle'
        self.course.save()
        ensure_draft_world(self.course)

        # Create a random test course with a title without the phrase "Test" in it
        CourseFactory(partner=self.partner, key=self.course.key + 'Z', title='RandomString')

        # There should be 3 courses, the specific key course, the draft, and the FakeKey
        courses = Course.everything.all()
        self.assertEqual(len(courses), 3)

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['uuid'], str(self.course.uuid))

    def test_list_pubq_by_key(self):
        """ Verify the endpoint returns a list of courses filtered by key when specified with pubq and editable """
        url = reverse('api:v1:course-list') + '?editable=1&pubq=ThisIsASpecificTestString'

        self.course.title = 'ThisIsASpecificTestStringKey'
        self.course.save()
        ensure_draft_world(self.course)

        # Create a random test course with a key without the phrase "Test" in it
        CourseFactory(partner=self.partner, key='FakeKey')

        # There should be 3 courses, the specific key course, the draft, and the FakeKey
        courses = Course.everything.all()
        self.assertEqual(len(courses), 3)

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['uuid'], str(self.course.uuid))

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
        ('get', False, True, False, True),
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
        assert response.status_code == 401
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

    def create_course_and_course_run(self, data=None, update=True):
        if update:
            course_data = {
                'number': 'test101',
                'org': self.org.key,
                'course_run': {
                    'start': '2001-01-01T00:00:00Z',
                    'end': datetime.datetime.now() + datetime.timedelta(days=1),
                }
            }
            course_data.update(data or {})
        else:
            course_data = data or {}

        responses.add(
            responses.POST,
            settings.BACKEND_SERVICE_EDX_OAUTH2_PROVIDER_URL + '/access_token',
            body=json.dumps({'access_token': 'abcd', 'expires_in': 60}),
            status=200,
        )
        studio_url = '{root}/api/v1/course_runs/'.format(root=self.partner.studio_url.strip('/'))
        responses.add(responses.POST, studio_url, status=200)
        key = 'course-v1:{org}+{number}+1T2001'.format(org=course_data['org'], number=course_data['number'])
        responses.add(responses.POST, '{url}{key}/images/'.format(url=studio_url, key=key), status=200)
        return self.create_course(course_data, update)

    @responses.activate
    def test_create_with_authentication_verified_mode(self):
        self.mock_access_token()
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

    def test_create_with_authentication_audit_mode(self):
        """
        When creating with audit mode, no entitlement should be created.
        """
        self.mock_access_token()
        response = self.create_course()

        course = Course.everything.last()
        self.assertDictEqual(response.data, self.serialize_course(course))
        self.assertEqual(response.status_code, 201)
        expected_course_key = '{org}+{number}'.format(org=self.org.key, number='test101')
        self.assertEqual(course.key, expected_course_key)
        self.assertEqual(course.title, 'Course title')
        self.assertListEqual(list(course.authoring_organizations.all()), [self.org])
        self.assertEqual(0, CourseEntitlement.objects.count())

    def test_create_makes_draft(self):
        """ When creating a course, it should start as a draft. """
        self.mock_access_token()
        response = self.create_course({'mode': 'verified', 'price': 77})
        self.assertEqual(response.status_code, 201)

        course = Course.everything.last()
        self.assertTrue(course.draft)
        self.assertTrue(course.entitlements.first().draft)

    def test_create_makes_editor(self):
        """ When creating a course, it should set the current user as the only editor for that course. """
        self.mock_access_token()
        response = self.create_course({'mode': 'verified'})
        self.assertEqual(response.status_code, 201)

        course = Course.everything.last()

        CourseEditor.objects.get(user=self.user, course=course)
        self.assertEqual(CourseEditor.objects.count(), 1)

    def test_create_makes_course_and_course_run(self):
        """
        When creating a course and supplying a course_run, it should create both the course
        and course run as drafts. When mode = 'audit', an audit seat should also be created.
        """
        response = self.create_course_and_course_run()
        self.assertEqual(response.status_code, 201)

        course = Course.everything.last()
        self.assertTrue(course.draft)
        self.assertTrue(course.entitlements.first().draft)
        course_run = CourseRun.everything.last()
        self.assertTrue(course_run.draft)
        self.assertEqual(course_run.course, course)

        # Creating with mode = 'audit' should also create an audit seat
        self.assertEqual(1, Seat.everything.count())  # pylint: disable=no-member
        seat = course_run.seats.first()
        self.assertEqual(seat.type, Seat.AUDIT)
        self.assertEqual(seat.price, 0.00)

    def test_create_with_course_run_makes_verified_seat(self):
        """
        When creating a course and supplying a course_run, it should create both the course
        and course run as drafts. When mode = 'verified', a verified seat and an audit seat should be created.
        """
        self.mock_access_token()
        data = {
            'number': 'test101',
            'org': self.org.key,
            'mode': 'verified',
            'price': 77.77,
            'course_run': {
                'start': '2001-01-01T00:00:00Z',
                'end': datetime.datetime.now() + datetime.timedelta(days=1),
            }
        }
        response = self.create_course_and_course_run(data)
        self.assertEqual(response.status_code, 201)

        course_run = CourseRun.everything.last()

        self.assertEqual(Seat.everything.count(), 2)  # pylint: disable=no-member
        verified_seat = Seat.everything.get(course_run=course_run, type='verified')  # pylint: disable=no-member
        self.assertEqual(float(verified_seat.price), data['price'])
        audit_seat = Seat.everything.get(course_run=course_run, type='audit')  # pylint: disable=no-member
        self.assertEqual(audit_seat.price, 0.00)
        self.assertTrue(audit_seat.draft)

    def test_create_fails_if_official_version_exists(self):
        """ When creating a course, it should not create one if an official version already exists. """
        self.mock_access_token()
        response = self.create_course({'number': 'Fake101'})
        self.assertEqual(response.status_code, 400)
        expected_error_message = 'Failed to set data: A course with key {key} already exists.'
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

    def test_create_fails_invalid_course_number(self):
        response = self.create_course({'number': 'a b c'})
        self.assertEqual(response.status_code, 400)
        expected_error_message = 'Failed to set data: Special characters not allowed in Course Number.'
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
                        'An error occurred while setting Course or Course Run data.',
                    )
                )

    def test_update_without_authentication(self):
        """ Verify authentication is required when updating a course. """
        self.client.logout()
        Course.objects.all().delete()

        url = reverse('api:v1:course-detail', kwargs={'key': self.course.uuid})
        response = self.client.patch(url)
        assert response.status_code == 401
        assert Course.objects.count() == 0

    @ddt.data('put', 'patch')
    @responses.activate
    def test_update_success(self, method):
        self.mock_access_token()
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

    @responses.activate
    def test_update_operates_on_drafts(self):
        self.mock_access_token()
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

    @responses.activate
    def test_patch_resets_run_status(self):
        self.mock_access_token()
        self.mock_ecommerce_publication()
        self.create_course_and_course_run()

        draft_course = Course.everything.last()
        draft_course_run = CourseRun.everything.last()
        draft_course_run.status = CourseRunStatus.Reviewed  # Triggers creation of official versions
        draft_course_run.save()
        official_course_run = draft_course_run.official_version
        self.assertEqual(official_course_run.status, CourseRunStatus.Reviewed)

        url = reverse('api:v1:course-detail', kwargs={'key': draft_course.uuid})
        patch_data = {
            'title': 'Title EDIT',
            'topics': ['tag1', 'tag2'],
        }
        response = self.client.patch(url, patch_data, format='json')
        self.assertEqual(response.status_code, 200)

        draft_course.refresh_from_db()
        draft_course_run.refresh_from_db()
        official_course_run.refresh_from_db()
        self.assertEqual(draft_course_run.status, CourseRunStatus.Unpublished)
        self.assertEqual(official_course_run.status, CourseRunStatus.Unpublished)

    @responses.activate
    def test_update_creates_draft_audit_entitlement_if_none_exists(self):
        """
        When an official version has no entitlements, it could be an audit course so we can create
        a draft audit entitlement. This happens as part of the call to ensure_draft_world.
        """
        self.mock_access_token()
        self.assertFalse(CourseEntitlement.everything.filter(course=self.course).exists())  # pylint: disable=no-member

        url = reverse('api:v1:course-detail', kwargs={'key': self.course.uuid})
        response = self.client.patch(url, {'entitlements': [{}]}, format='json')
        self.assertEqual(response.status_code, 200)

        course = Course.everything.get(uuid=self.course.uuid, draft=True)
        entitlement = course.entitlements.first()
        self.assertTrue(entitlement.draft)
        self.assertEqual(entitlement.mode.slug, Seat.AUDIT)
        self.assertEqual(entitlement.price, 0.00)

        self.course.refresh_from_db()
        self.assertFalse(self.course.draft)
        self.assertFalse(self.course.entitlements.exists())

    @responses.activate
    def test_patch_published(self):
        """
        Verify that draft rows can be updated and re-published with draft=False. This should also
        update and publish the official version.
        """
        self.mock_access_token()
        self.mock_ecommerce_publication()
        data = {
            'mode': 'verified',
            'price': 49,
        }
        self.create_course_and_course_run(data)

        draft_course = Course.everything.last()
        draft_course_run = CourseRun.everything.last()
        draft_course_run.status = CourseRunStatus.Reviewed  # Triggers creation of official versions
        draft_course_run.save()
        # Only updates to official when there is a Published Course Run
        draft_course_run.status = CourseRunStatus.Published
        draft_course_run.save()

        # Edit; should only touch draft
        url = reverse('api:v1:course-detail', kwargs={'key': draft_course.uuid})
        updated_short_desc = 'New short desc'
        data = {
            'short_description': updated_short_desc,
        }
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, 200)

        official_course = Course.everything.get(uuid=draft_course.uuid, draft=False)
        draft_course = official_course.draft_version

        self.assertEqual(draft_course.short_description, updated_short_desc)
        self.assertNotEqual(official_course.short_description, updated_short_desc)

        # Re-publish; should update official with new and old information
        updated_full_desc = 'New long desc'
        response = self.client.patch(url, {'full_description': updated_full_desc, 'draft': False}, format='json')
        self.assertEqual(response.status_code, 200)

        draft_course.refresh_from_db()
        official_course.refresh_from_db()
        self.assertEqual(draft_course.short_description, updated_short_desc)
        self.assertEqual(official_course.short_description, updated_short_desc)
        self.assertEqual(draft_course.full_description, updated_full_desc)
        self.assertEqual(official_course.full_description, updated_full_desc)

        entitlement = draft_course.entitlements.first()
        updated_entitlement = {
            'mode': entitlement.mode.slug,
            'price': 1000,
        }
        response = self.client.patch(url, {'entitlements': [updated_entitlement], 'draft': False}, format='json')
        self.assertEqual(response.status_code, 200)

        draft_course.refresh_from_db()
        official_course.refresh_from_db()
        self.assertEqual(draft_course.entitlements.first().price, updated_entitlement['price'])
        self.assertEqual(official_course.entitlements.first().price, updated_entitlement['price'])

    @responses.activate
    def test_patch_published_switch_audit_to_verified(self):
        """
        Verify that draft rows can be updated and re-published with draft=False. This should also
        update and publish the official version.
        """
        self.mock_access_token()
        self.mock_ecommerce_publication()
        self.create_course_and_course_run()

        draft_course = Course.everything.last()
        draft_course_run = CourseRun.everything.last()
        draft_course_run.status = CourseRunStatus.Reviewed  # Triggers creation of official versions
        draft_course_run.save()
        # Only updates to official when there is a Published Course Run
        draft_course_run.status = CourseRunStatus.Published
        draft_course_run.save()

        official_course = Course.everything.get(uuid=draft_course.uuid, draft=False)
        draft_course = official_course.draft_version

        # We only expect the draft course to have an entitlement since we don't create official Audit entitlements
        self.assertEqual(CourseEntitlement.everything.count(), 1)  # pylint: disable=no-member
        self.assertEqual(draft_course.entitlements.first().mode.slug, 'audit')
        self.assertTrue(draft_course.entitlements.first().draft)
        self.assertIsNone(official_course.entitlements.first())

        # We expect the draft course run and the official course run to now both have audit Seats
        official_course_run = CourseRun.objects.get(key=draft_course_run.key)
        draft_course_run = official_course_run.draft_version
        self.assertEqual(Seat.everything.count(), 2)  # pylint: disable=no-member
        self.assertEqual(draft_course_run.seats.first().type, 'audit')
        self.assertTrue(draft_course_run.seats.first().draft)
        self.assertEqual(official_course_run.seats.first().type, 'audit')
        self.assertFalse(official_course_run.seats.first().draft)

        # Republish with a verified slug
        url = reverse('api:v1:course-detail', kwargs={'key': draft_course.uuid})
        updated_entitlement = {
            'mode': SeatType.objects.get(slug='verified').slug,
            'price': 1000,
        }
        response = self.client.patch(url, {'entitlements': [updated_entitlement], 'draft': False}, format='json')
        self.assertEqual(response.status_code, 200)

        draft_course.refresh_from_db()
        official_course.refresh_from_db()
        self.assertEqual(CourseEntitlement.everything.count(), 2)  # pylint: disable=no-member
        self.assertEqual(draft_course.entitlements.first().price, updated_entitlement['price'])
        self.assertEqual(draft_course.entitlements.first().mode.slug, updated_entitlement['mode'])
        self.assertEqual(official_course.entitlements.first().price, updated_entitlement['price'])
        self.assertEqual(official_course.entitlements.first().mode.slug, updated_entitlement['mode'])

        draft_course_run.refresh_from_db()
        official_course_run.refresh_from_db()
        # Verified means there should be both an Audit seat and Verified seat
        self.assertEqual(Seat.everything.count(), 4)  # pylint: disable=no-member
        draft_verified_seat = Seat.everything.get(course_run=draft_course_run, type='verified')  # pylint: disable=no-member
        self.assertEqual(float(draft_verified_seat.price), updated_entitlement['price'])
        draft_audit_seat = Seat.everything.get(course_run=draft_course_run, type='audit')  # pylint: disable=no-member
        self.assertEqual(draft_audit_seat.price, 0.00)

        official_verified_seat = Seat.everything.get(course_run=official_course_run, type='verified')  # pylint: disable=no-member
        self.assertEqual(float(official_verified_seat.price), updated_entitlement['price'])
        official_audit_seat = Seat.everything.get(course_run=official_course_run, type='audit')  # pylint: disable=no-member
        self.assertEqual(official_audit_seat.price, 0.00)

    @ddt.data(
        ('audit', 'audit', 0.00),
        ('audit', 'verified', 77),
        ('audit', 'professional', 132),
        ('verified', 'audit', 0.00),
        ('verified', 'verified', 77),
        ('verified', 'professional', 132),
        ('professional', 'audit', 0.00),
        ('professional', 'verified', 77),
        ('professional', 'professional', 132),
    )
    @ddt.unpack
    @responses.activate
    def test_patch_updating_entitlements_also_updates_seats(self, original_mode, mode, price):
        """
        Verify that draft rows can be updated and re-published with draft=False. This should also
        update and publish the official version.
        """
        self.mock_access_token()
        data = {
            'mode': original_mode,
            'price': 49,
        }
        self.create_course_and_course_run(data)

        draft_course = Course.everything.last()
        draft_course_run = CourseRun.everything.last()

        url = reverse('api:v1:course-detail', kwargs={'key': draft_course.uuid})
        updated_entitlement = {
            'mode': mode,
            'price': price,
        }
        response = self.client.patch(url, {'entitlements': [updated_entitlement], 'draft': False}, format='json')
        self.assertEqual(response.status_code, 200)

        num_seats = Seat.everything.count()  # pylint: disable=no-member
        if mode == 'verified':
            self.assertEqual(num_seats, 2)
            audit_seat = Seat.everything.get(course_run=draft_course_run, type='audit')  # pylint: disable=no-member
            self.assertEqual(audit_seat.price, 0.00)
            self.assertTrue(audit_seat.draft)
        else:
            self.assertEqual(num_seats, 1)
        seat = Seat.everything.get(course_run=draft_course_run, type=mode)  # pylint: disable=no-member
        self.assertEqual(seat.price, price)
        self.assertTrue(seat.draft)

    @ddt.data(
        (
            {'entitlements': [{'price': 5}]},
            'Entitlements must have a mode specified.',
        ),
        (
            {'entitlements': [{'mode': 'NOPE'}]},
            'Entitlement mode NOPE not found.'
        ),
        (
            {'entitlements': [{'mode': 'mode2'}]},
            'Switching entitlement modes after being reviewed is not supported. Please reach out to your '
            'project coordinator for additional help if necessary.'
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
                        'An error occurred while setting Course or Course Run data.',
                    )
                )

    @responses.activate
    def test_options(self):
        self.mock_access_token()
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
        self.assertNotIn('choices', data['partner'])  # we don't whitelist partner to show its choices

    @responses.activate
    @ddt.data(True, False)
    def test_retrieve_will_create_entitlement(self, has_entitlement):
        """ When retrieving a course, test that an entitlement gets created if needed """
        self.mock_access_token()

        self.assertFalse(self.course.entitlements.exists())  # sanity check

        run = CourseRunFactory(course=self.course)
        SeatFactory(type=Seat.VERIFIED, course_run=run, price=40)
        if has_entitlement:
            CourseEntitlementFactory(course=self.course, price=40, mode=SeatType.objects.get(slug=Seat.VERIFIED))

        url = reverse('api:v1:course-detail', kwargs={'key': self.course.uuid})

        # First, without editable=1, to confirm we never do anything there
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.course.entitlements.exists(), has_entitlement)

        # Now with editable=1 for real
        response = self.client.get(url, {'editable': 1})

        self.assertEqual(response.status_code, 200)
        self.assertIn('entitlements', response.json())
        self.assertEqual(len(response.json()['entitlements']), 1)
        self.assertTrue(self.course.entitlements.exists())
        self.assertEqual(self.course.entitlements.first().mode.slug, Seat.VERIFIED)
        self.assertEqual(self.course.entitlements.first().price, 40)
