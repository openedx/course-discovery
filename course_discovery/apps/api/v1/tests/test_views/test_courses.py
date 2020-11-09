import datetime
import json
from unittest import mock

import ddt
import pytest
import pytz
import responses
from django.conf import settings
from django.db import IntegrityError
from django.db.models.functions import Lower
from rest_framework.reverse import reverse
from testfixtures import LogCapture

from course_discovery.apps.api.v1.exceptions import EditableAndQUnsupported
from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase, OAuth2Mixin, SerializationMixin
from course_discovery.apps.api.v1.views.courses import logger as course_logger
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.choices import CourseRunStatus, ProgramStatus
from course_discovery.apps.course_metadata.models import (
    Course, CourseEditor, CourseEntitlement, CourseRun, CourseRunType, CourseType, Seat
)
from course_discovery.apps.course_metadata.tests.factories import (
    CourseEditorFactory, CourseEntitlementFactory, CourseFactory, CourseRunFactory, LevelTypeFactory,
    OrganizationFactory, ProgramFactory, SeatFactory, SeatTypeFactory, SubjectFactory
)
from course_discovery.apps.course_metadata.utils import ensure_draft_world
from course_discovery.apps.publisher.tests.factories import OrganizationExtensionFactory


@ddt.ddt
@pytest.mark.usefixtures('django_cache')
class CourseViewSetTests(OAuth2Mixin, SerializationMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.user = UserFactory(is_staff=True)
        self.request.user = self.user
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.audit_type = CourseType.objects.get(slug=CourseType.AUDIT)
        self.verified_type = CourseType.objects.get(slug=CourseType.VERIFIED_AUDIT)
        self.course = CourseFactory(partner=self.partner, title='Fake Test', key='edX+Fake101', type=self.audit_type)
        self.org = OrganizationFactory(key='edX', partner=self.partner)
        self.course.authoring_organizations.add(self.org)

    def tearDown(self):
        super().tearDown()
        self.client.logout()

    def mock_ecommerce_publication(self):
        url = f'{self.course.partner.ecommerce_api_url}publication/'
        responses.add(responses.POST, url, json={}, status=200)

    def test_get(self):
        """ Verify the endpoint returns the details for a single course. """
        url = reverse('api:v1:course-detail', kwargs={'key': self.course.key})

        with self.assertNumQueries(37):
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.serialize_course(self.course))

    def test_get_uuid(self):
        """ Verify the endpoint returns the details for a single course with UUID. """
        url = reverse('api:v1:course-detail', kwargs={'key': self.course.uuid})

        with self.assertNumQueries(37):
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.serialize_course(self.course))

    def test_get_exclude_deleted_programs(self):
        """ Verify the endpoint returns no deleted associated programs """
        ProgramFactory(courses=[self.course], status=ProgramStatus.Deleted)
        url = reverse('api:v1:course-detail', kwargs={'key': self.course.key})
        with self.assertNumQueries(37):
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
        with self.assertNumQueries(40):
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
        url = f'{url}?marketable_course_runs_only={marketable_course_runs_only}'
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
        url = f'{url}?published_course_runs_only={published_course_runs_only}'

        response = self.client.get(url)

        assert response.status_code == 200

        if published_course_runs_only:
            # Emulate prefetching behavior.
            unpublished_course_run.delete()

        assert response.data == self.serialize_course(self.course)

    def test_list(self):
        """ Verify the endpoint returns a list of all courses. """
        url = reverse('api:v1:course-list')

        with self.assertNumQueries(25):
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

        # Known to be flaky prior to the addition of tearDown()
        # and logout() code which is the same number of additional queries
        with self.assertNumQueries(42):
            response = self.client.get(url)
        self.assertListEqual(response.data['results'], self.serialize_course(courses, many=True))

    def test_list_key_filter(self):
        """ Verify the endpoint returns a list of courses filtered by the specified keys. """
        courses = CourseFactory.create_batch(3, partner=self.partner)
        courses = sorted(courses, key=lambda course: course.key.lower())
        keys = ','.join([course.key for course in courses])
        url = '{root}?keys={keys}'.format(root=reverse('api:v1:course-list'), keys=keys)

        with self.assertNumQueries(42):
            response = self.client.get(url)
        self.assertListEqual(response.data['results'], self.serialize_course(courses, many=True))

    def test_list_uuid_filter(self):
        """ Verify the endpoint returns a list of courses filtered by the specified uuid. """
        courses = CourseFactory.create_batch(3, partner=self.partner)
        courses = sorted(courses, key=lambda course: course.key.lower())
        uuids = ','.join([str(course.uuid) for course in courses])
        url = '{root}?uuids={uuids}'.format(root=reverse('api:v1:course-list'), uuids=uuids)

        with self.assertNumQueries(42):
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

    def test_list_course_run_statuses(self):
        """ Verify the endpoint returns a list of courses by course run status """
        url = reverse('api:v1:course-list') + '?editable=1&course_run_statuses=unpublished'
        CourseRunFactory(status=CourseRunStatus.Unpublished, course=self.course)
        ensure_draft_world(self.course)

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['uuid'], str(self.course.uuid))

        course2 = CourseFactory()
        url2 = reverse('api:v1:course-list') + '?editable=1&course_run_statuses=in_review'
        CourseRunFactory(status=CourseRunStatus.LegalReview, course=course2)
        ensure_draft_world(course2)

        response2 = self.client.get(url2)
        self.assertEqual(response2.status_code, 200)
        self.assertEqual(len(response2.data['results']), 1)
        self.assertEqual(response2.data['results'][0]['uuid'], str(course2.uuid))

    def test_unsubmitted_status(self):
        """ Verify we support composite status 'unsubmitted' (unpublished & unarchived). """
        self.course.delete()
        now = datetime.datetime.now(pytz.UTC)
        no_end_run = ensure_draft_world(CourseRunFactory(status=CourseRunStatus.Unpublished, end=None))
        _past_end_run = ensure_draft_world(CourseRunFactory(status=CourseRunStatus.Unpublished,
                                                            end=now - datetime.timedelta(days=1)))
        future_end_run = ensure_draft_world(CourseRunFactory(status=CourseRunStatus.Unpublished,
                                                             end=now + datetime.timedelta(days=1)))

        response = self.client.get(reverse('api:v1:course-list') + '?editable=1&course_run_statuses=unsubmitted')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 2)
        self.assertEqual({c['uuid'] for c in response.data['results']},
                         {str(run.course.uuid) for run in [future_end_run, no_end_run]})

    def test_no_archived_statuses(self):
        """ Verify that we skip archived statuses in a course serialization of statuses. """
        now = datetime.datetime.now(pytz.UTC)
        past_end_run = CourseRunFactory(course=self.course, status=CourseRunStatus.Unpublished,
                                        end=now - datetime.timedelta(days=1))
        _published_run = CourseRunFactory(course=self.course, status=CourseRunStatus.Published)

        response = self.client.get(reverse('api:v1:course-list'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['uuid'], str(self.course.uuid))
        self.assertEqual(response.data['results'][0]['course_run_statuses'], ['published'])  # no 'unpublished' status

        # Now test with no end date - we should see unarchived appear
        past_end_run.end = None
        past_end_run.save()
        response = self.client.get(reverse('api:v1:course-list'))
        self.assertEqual(response.data['results'][0]['course_run_statuses'], ['published', 'unpublished'])

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
        # We'll probably fail with 400 because we didn't include the right data - but at least confirm we got in
        self.assertEqual(response.status_code not in [403, 404], allowed, response.status_code)

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

    def test_editable_list_shows_all_courses_in_org(self):
        """ Even ones we're not an editor for. """
        # Add the real editor for this course
        org_ext = OrganizationExtensionFactory(organization=self.org)
        user2 = UserFactory()
        user2.groups.add(org_ext.group)
        CourseEditorFactory(user=user2, course=self.course)

        self.user.groups.add(org_ext.group)
        self.user.is_staff = False
        self.user.save()

        self.assertFalse(CourseEditor.is_course_editable(self.user, self.course))  # sanity check

        response = self.client.get(reverse('api:v1:course-list') + '?editable=1')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['results'], self.serialize_course([self.course], many=True))

    @responses.activate
    def test_editable_list_is_denied_as_normal_user(self):
        """ Verify that GET with editable=1 can't be reached by a normal unprivileged user. """
        self.user.is_staff = False
        self.user.save()

        response = self.client.get(reverse('api:v1:course-list') + '?editable=1')
        self.assertEqual(response.status_code, 403)

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

    def test_editable_get_shows_editable_status(self):
        # Add the real editor for this course
        org_ext = OrganizationExtensionFactory(organization=self.org)
        user2 = UserFactory()
        user2.groups.add(org_ext.group)
        editor = CourseEditorFactory(user=user2, course=self.course)

        self.user.groups.add(org_ext.group)
        self.user.is_staff = False
        self.user.save()

        self.assertFalse(CourseEditor.is_course_editable(self.user, self.course))  # sanity check
        response = self.client.get(reverse('api:v1:course-detail', kwargs={'key': self.course.uuid}) + '?editable=1')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['editable'])

        editor.delete()
        self.assertTrue(CourseEditor.is_course_editable(self.user, self.course))  # sanity check
        response = self.client.get(reverse('api:v1:course-detail', kwargs={'key': self.course.uuid}) + '?editable=1')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['editable'])

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
        self.assertEqual(self.client.patch(url).status_code, 403)

        # Add to authoring org, and we should be let in
        org_ext = OrganizationExtensionFactory(organization=self.org)
        self.user.groups.add(org_ext.group)
        self.assertNotEqual(self.client.patch(url).status_code, 403)

        # Now add a random other user as an editor to the course, so that we will no longer be granted access.
        editor = UserFactory()
        CourseEditorFactory(user=editor, course=self.course)
        editor.groups.add(org_ext.group)
        self.assertEqual(self.client.patch(url).status_code, 404)

        # But if the editor is no longer valid (even though they exist), we're back to having access.
        editor.groups.remove(org_ext.group)
        self.assertNotEqual(self.client.patch(url).status_code, 403)

        # And finally, for a sanity check, confirm we have access when we become an editor also
        CourseEditorFactory(user=self.user, course=self.course)
        self.assertNotEqual(self.client.patch(url).status_code, 403)

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
                'type': str(self.audit_type.uuid),
            }
            course_data.update(data or {})
        else:
            course_data = data or {}
        return self.client.post(url, course_data, format='json')

    def create_course_and_course_run(self, data=None, update=True):
        if update:
            course_data = {
                'title': 'Course title',
                'number': 'test101',
                'org': self.org.key,
                'type': str(self.audit_type.uuid),
                'course_run': {
                    'start': '2001-01-01T00:00:00Z',
                    'end': datetime.datetime.now() + datetime.timedelta(days=1),
                    'run_type': str(CourseRunType.objects.get(slug=CourseRunType.AUDIT).uuid),
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
        responses.add(responses.POST, f'{studio_url}{key}/images/', status=200)
        return self.create_course(course_data, update)

    def test_multiple_authoring_orgs_get_pulled_in_order(self):
        org1 = OrganizationFactory(key='org1', partner=self.partner)
        org2 = OrganizationFactory(key='org2', partner=self.partner)
        org3 = OrganizationFactory(key='org3', partner=self.partner)

        course = CourseFactory(partner=self.partner,
                               title='Mult Org Course',
                               key='edX+6688',
                               type=self.audit_type,
                               authoring_organizations=[org1, org2, org3])

        self.mock_access_token()

        url = reverse('api:v1:course-detail', kwargs={'key': course.key})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.data['owners'][0]['key'], 'org1')
        self.assertEqual(response.data['owners'][1]['key'], 'org2')
        self.assertEqual(response.data['owners'][2]['key'], 'org3')

        course.authoring_organizations.clear()
        for org in [org2, org3, org1]:
            course.authoring_organizations.add(org)

        url = reverse('api:v1:course-detail', kwargs={'key': course.key})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.data['owners'][0]['key'], 'org2')
        self.assertEqual(response.data['owners'][1]['key'], 'org3')
        self.assertEqual(response.data['owners'][2]['key'], 'org1')

    def test_create_makes_draft(self):
        """ When creating a course, it should start as a draft. """
        self.mock_access_token()
        response = self.create_course({'type': str(self.verified_type.uuid), 'prices': {'verified': 77}})
        self.assertEqual(response.status_code, 201)

        course = Course.everything.last()
        self.assertTrue(course.draft)
        self.assertTrue(course.entitlements.first().draft)

    def test_create_makes_editor(self):
        """ When creating a course, it should set the current user as the only editor for that course. """
        self.mock_access_token()
        response = self.create_course()
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
        self.assertIsNone(course.entitlements.first())
        course_run = CourseRun.everything.last()
        self.assertTrue(course_run.draft)
        self.assertEqual(course_run.course, course)

        # Creating with mode = 'audit' should also create an audit seat
        self.assertEqual(1, Seat.everything.count())
        seat = course_run.seats.first()
        self.assertEqual(seat.type.slug, Seat.AUDIT)
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
            'type': str(CourseType.objects.get(slug=CourseType.VERIFIED_AUDIT).uuid),
            'prices': {'verified': 77.77},
            'course_run': {
                'start': '2001-01-01T00:00:00Z',
                'end': datetime.datetime.now() + datetime.timedelta(days=1),
                'run_type': str(CourseRunType.objects.get(slug=CourseRunType.VERIFIED_AUDIT).uuid),
            }
        }
        response = self.create_course_and_course_run(data)
        self.assertEqual(response.status_code, 201)

        course_run = CourseRun.everything.last()

        self.assertEqual(Seat.everything.count(), 2)
        verified_seat = Seat.everything.get(course_run=course_run, type='verified')
        self.assertEqual(float(verified_seat.price), 77.77)
        audit_seat = Seat.everything.get(course_run=course_run, type='audit')
        self.assertEqual(audit_seat.price, 0.00)
        self.assertTrue(audit_seat.draft)

    def test_create_auto_creates_slug_if_not_set(self):
        self.mock_access_token()
        response = self.create_course()
        self.assertEqual(response.status_code, 201)
        course = Course.everything.last()
        course.refresh_from_db()
        self.assertEqual(course.active_url_slug, 'course-title')

    def test_add_collaborator_uuid_list(self):
        self.mock_access_token()
        collaborator = {
            'name': 'Collaborator 1',
            # The API is expecting the image to be base64 encoded. We are simulating that here.
            'image': 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY'
                     '42YAAAAASUVORK5CYII=',
        }
        collaborator_url = reverse('api:v1:collaborator-list')
        collab_post_response = self.client.post(collaborator_url, collaborator, format='json')
        self.assertEqual(collab_post_response.status_code, 201)
        get_collab_response = self.client.get(collaborator_url)
        collab_json = get_collab_response.json()
        self.assertEqual(len(collab_json['results']), 1)
        collaborator_to_use = collab_json['results'][0]
        response = self.create_course({'collaborators': [collaborator_to_use['uuid']]})
        self.assertEqual(response.status_code, 201)
        course = response.json()
        self.assertEqual(course['collaborators'][0]['name'], 'Collaborator 1')

    def test_modify_collaborator_uuid_list(self):
        self.mock_access_token()
        collaborator = {
            'name': 'Collaborator 1',
            # The API is expecting the image to be base64 encoded. We are simulating that here.
            'image': 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY'
                     '42YAAAAASUVORK5CYII=',
        }
        collaborator2 = {
            'name': 'Collaborator 2',
            # The API is expecting the image to be base64 encoded. We are simulating that here.
            'image': 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY'
                     '42YAAAAASUVORK5CYII=',
        }
        collaborator_url = reverse('api:v1:collaborator-list')
        collab_post_response = self.client.post(collaborator_url, collaborator, format='json')
        collab_post_response2 = self.client.post(collaborator_url, collaborator2, format='json')
        self.assertEqual(collab_post_response.status_code, 201)
        get_collab_response = self.client.get(collaborator_url)
        collab_json = get_collab_response.json()
        self.assertEqual(len(collab_json['results']), 2)
        collaborator_to_use = collab_json['results'][0]
        response = self.create_course({'collaborators': [collaborator_to_use['uuid']]})
        self.assertEqual(response.status_code, 201)
        course = response.json()
        collab1 = collab_post_response.json()
        collab2 = collab_post_response2.json()
        self.assertEqual(course['collaborators'][0]['uuid'], collaborator_to_use['uuid'])
        course_url = reverse('api:v1:course-detail', kwargs={'key': course['uuid']})
        modify_course_data = {'collaborators': [collab1['uuid'], collab2['uuid']]}
        response = self.client.patch(course_url, modify_course_data, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['collaborators']), 2)

    def test_create_saves_manual_url_slug(self):
        self.mock_access_token()
        response = self.create_course({'url_slug': 'manual'})
        self.assertEqual(response.status_code, 201)
        course = Course.everything.last()
        self.assertEqual(course.active_url_slug, 'manual')

    def test_create_increments_auto_url_slug(self):
        self.mock_access_token()
        response = self.create_course()
        self.assertEqual(response.status_code, 201)
        course = Course.everything.last()
        self.assertEqual(course.active_url_slug, 'course-title')

        response = self.create_course({'number': 'a123'})
        self.assertEqual(response.status_code, 201)
        course = Course.everything.last()
        self.assertEqual(course.active_url_slug, 'course-title-2')

    def test_create_with_course_type_verified(self):
        self.mock_access_token()
        data = {
            'title': 'Test Course',
            'number': 'test101',
            'org': self.org.key,
            'type': str(self.verified_type.uuid),
            'prices': {'verified': 77},
        }
        response = self.create_course(data, update=False)

        course = Course.everything.last()
        self.assertDictEqual(response.data, self.serialize_course(course))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(course.title, data['title'])
        self.assertEqual(course.type, self.verified_type)

        self.assertEqual(1, CourseEntitlement.everything.count())
        entitlement = course.entitlements.last()
        self.assertEqual(entitlement.mode.slug, Seat.VERIFIED)
        self.assertEqual(entitlement.price, 77)

    def test_create_with_course_type_audit(self):
        self.mock_access_token()
        data = {
            'title': 'Test Course',
            'number': 'test101',
            'org': self.org.key,
            'type': str(self.audit_type.uuid),
        }
        response = self.create_course(data, update=False)

        course = Course.everything.last()
        self.assertDictEqual(response.data, self.serialize_course(course))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(course.title, data['title'])
        self.assertEqual(course.type, self.audit_type)
        self.assertEqual(0, CourseEntitlement.everything.count())

    def test_create_fails_if_manual_slug_exists(self):
        self.mock_access_token()
        response = self.create_course()
        self.assertEqual(response.status_code, 201)
        course = Course.everything.last()
        self.assertEqual(course.active_url_slug, 'course-title')

        response = self.create_course({'url_slug': 'course-title', 'number': 'a123'})
        self.assertEqual(response.status_code, 400)
        expected_error_message = 'Failed to set data: Course creation was unsuccessful. ' \
                                 'The course URL slug ‘[course-title]’ is already in use. ' \
                                 'Please update this field and try again.'
        self.assertEqual(response.data, expected_error_message)

    def test_create_fails_if_official_version_exists(self):
        """ When creating a course, it should not create one if an official version already exists. """
        self.mock_access_token()
        response = self.create_course({'number': 'Fake101'})
        self.assertEqual(response.status_code, 400)
        expected_error_message = 'Failed to set data: A course with key [{key}] already exists.'
        self.assertEqual(response.data, expected_error_message.format(key=self.course.key))

    def test_create_fails_with_missing_field(self):
        response = self.create_course(
            {
                'title': 'Course title',
                'org': self.org.key,
                'type': str(self.audit_type.uuid),
            },
            update=False
        )
        self.assertEqual(response.status_code, 400)
        expected_error_message = 'Incorrect data sent. Missing value for: [number].'
        self.assertEqual(response.data, expected_error_message)

    def test_create_fails_with_nonexistent_org(self):
        response = self.create_course({'org': 'fake org'})
        self.assertEqual(response.status_code, 400)
        expected_error_message = 'Incorrect data sent. Organization [fake org] does not exist.'
        self.assertEqual(response.data, expected_error_message)

    def test_create_fails_with_nonexistent_course_type(self):
        data = {
            'title': 'Test Course',
            'number': 'test101',
            'org': self.org.key,
            'type': '00000000-0000-0000-0000-000000000000',
        }
        response = self.create_course(data, update=False)
        self.assertEqual(response.status_code, 400)
        expected_error_message = 'Incorrect data sent. Course Type [' + data['type'] + '] does not exist.'
        self.assertEqual(response.data, expected_error_message)

    def test_create_fails_invalid_course_number(self):
        response = self.create_course({'number': 'a b c'})
        self.assertEqual(response.status_code, 400)
        expected_error_message = 'Failed to set data: Special characters not allowed in Course Number.'
        self.assertEqual(response.data, expected_error_message)

    @ddt.data(
        (
            {'title': 'Course title', 'number': 'test101', 'org': 'fake org',
             'type': '00000000-0000-0000-0000-000000000000'},
            'Incorrect data sent. Organization [fake org] does not exist. '
            'Course Type [00000000-0000-0000-0000-000000000000] does not exist.'
        ),
        (
            {'title': 'Course title', 'org': 'edX', 'type': '00000000-0000-0000-0000-000000000000'},
            'Incorrect data sent. Missing value for: [number]. '
            'Course Type [00000000-0000-0000-0000-000000000000] does not exist.'
        ),
        (
            {'title': 'Course title', 'org': 'fake org', 'type': 'audit'},
            'Incorrect data sent. Missing value for: [number]. Organization [fake org] does not exist.'
        ),
        (
            {'number': 'test101', 'org': 'fake org', 'type': '00000000-0000-0000-0000-000000000000'},
            'Incorrect data sent. Missing value for: [title]. Organization [fake org] does not exist. '
            'Course Type [00000000-0000-0000-0000-000000000000] does not exist.'
        ),
    )
    @ddt.unpack
    def test_create_fails_with_multiple_errors(self, course_data, expected_error_message):
        if course_data.get('type') == 'audit':
            course_data['type'] = str(self.audit_type.uuid)
        response = self.create_course(course_data, update=False)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, expected_error_message)

    def test_create_fails_if_run_creation_fails(self):
        '''
        For clarity, this only applies for when the course run endpoint receives an error response
        from Studio. Other errors (PermissionDenied, ValidationError, Http404) are all caught and
        raised to the course endpoint, but some errors just create a response.
        '''
        studio_url = '{root}/api/v1/course_runs/'.format(root=self.partner.studio_url.strip('/'))
        responses.add(responses.POST, studio_url, status=400, body=b'Nope')
        response = self.create_course_and_course_run()
        self.assertEqual(response.status_code, 400)
        expected_error_message = 'Failed to set data: Failed to set course run data: Nope'
        self.assertEqual(response.data, expected_error_message)

    def test_create_with_api_exception(self):
        with mock.patch(
            # We are using get_course_key because it is called prior to trying to contact the
            # e-commerce service and still gives the effect of an api exception.
            'course_discovery.apps.api.v1.views.courses.CourseViewSet.get_course_key',
            side_effect=IntegrityError('Error')
        ):
            with LogCapture(course_logger.name) as log_capture:
                response = self.create_course()
                self.assertEqual(response.status_code, 400)
                log_capture.check(
                    (
                        course_logger.name,
                        'ERROR',
                        'Failed to set data: Error',
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
        url = reverse('api:v1:course-detail', kwargs={'key': self.course.uuid})
        course_data = {
            'title': 'Course title',
            'url_slug': 'manual',
            'partner': self.partner.id,
            'key': self.course.key,
            'type': str(self.audit_type.uuid),
            # The API is expecting the image to be base64 encoded. We are simulating that here.
            'image': 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY'
                     '42YAAAAASUVORK5CYII=',
            'video': {'src': 'https://link.to.video.for.testing/watch?t_s=5'},
        }

        response = getattr(self.client, method)(url, course_data, format='json')
        self.assertEqual(response.status_code, 200)

        course = Course.everything.get(uuid=self.course.uuid, draft=True)
        self.assertEqual(course.title, 'Course title')
        self.assertEqual(course.active_url_slug, 'manual')
        self.assertDictEqual(response.data, self.serialize_course(course))

    @responses.activate
    def test_update_with_level_type(self):
        beginner = LevelTypeFactory()
        beginner.set_current_language('en')
        beginner.name_t = 'Beginner'
        beginner.save()
        self.mock_access_token()
        url = reverse('api:v1:course-detail', kwargs={'key': self.course.uuid})
        course_data = {
            'level_type': 'Beginner'
        }
        response = self.client.patch(url, course_data, format='json')
        self.assertEqual(response.status_code, 200)
        course = Course.everything.get(uuid=self.course.uuid, draft=True)
        self.assertEqual(course.level_type, beginner)

    @responses.activate
    def test_update_success_with_course_type_verified(self):
        self.mock_access_token()
        verified_mode = SeatTypeFactory.verified()
        CourseEntitlementFactory(course=self.course, mode=verified_mode)
        url = reverse('api:v1:course-detail', kwargs={'key': self.course.uuid})
        course_data = {
            'title': 'Course title',
            'key': self.course.key,
            'type': str(self.verified_type.uuid),
            'prices': {'verified': '77.32'},
        }

        response = self.client.patch(url, course_data, format='json')
        self.assertEqual(response.status_code, 200)

        course = Course.everything.get(uuid=self.course.uuid, draft=True)
        self.assertDictEqual(response.data, self.serialize_course(course))
        self.assertEqual(course.title, 'Course title')
        entitlement = course.entitlements.first()
        self.assertEqual(float(entitlement.price), 77.32)
        self.assertEqual(entitlement.mode.slug, Seat.VERIFIED)

    @responses.activate
    def test_update_success_with_course_type_audit(self):
        self.mock_access_token()
        url = reverse('api:v1:course-detail', kwargs={'key': self.course.uuid})
        course_data = {
            'title': 'Course title',
            'key': self.course.key,
            'type': str(self.audit_type.uuid),
        }

        response = self.client.patch(url, course_data, format='json')
        self.assertEqual(response.status_code, 200)

        course = Course.everything.get(uuid=self.course.uuid, draft=True)
        self.assertDictEqual(response.data, self.serialize_course(course))
        self.assertEqual(course.title, 'Course title')
        self.assertEqual(0, course.entitlements.count())

    def test_update_keeps_url_slug_if_removed_from_form(self):
        self.mock_access_token()
        self.course.set_active_url_slug('fake-test')
        url = reverse('api:v1:course-detail', kwargs={'key': self.course.uuid})
        course_data = {
            'url_slug': ''
        }
        response = self.client.patch(url, course_data, format='json')
        self.assertEqual(response.status_code, 200)
        course = Course.everything.get(uuid=self.course.uuid, draft=True)
        self.assertEqual(course.active_url_slug, 'fake-test')

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
        self.assertDictEqual(response.data, self.serialize_course(course))

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
    def test_patch_non_review_fields_does_not_reset_run_status(self):
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
            # The API is expecting the image to be base64 encoded. We are simulating that here.
            'image': 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY'
                     '42YAAAAASUVORK5CYII=',
            'video': {'src': 'https://new-videos-r-us/watch?t_s=5'},
        }
        response = self.client.patch(url, patch_data, format='json')
        self.assertEqual(response.status_code, 200)

        draft_course.refresh_from_db()
        draft_course_run.refresh_from_db()
        official_course_run.refresh_from_db()
        self.assertEqual(draft_course_run.status, CourseRunStatus.Reviewed)
        self.assertEqual(official_course_run.status, CourseRunStatus.Reviewed)

    @responses.activate
    def test_patch_published(self):
        """
        Verify that draft rows can be updated and re-published with draft=False. This should also
        update and publish the official version.
        """
        self.mock_access_token()
        self.mock_ecommerce_publication()
        data = {
            'type': str(CourseType.objects.get(slug=CourseType.VERIFIED_AUDIT).uuid),
            'prices': {
                'verified': 40,
            },
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
        updated_short_desc = '<p>New short desc</p>'
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
        updated_full_desc = '<p>New long desc</p>'
        response = self.client.patch(url, {'full_description': updated_full_desc, 'draft': False}, format='json')
        self.assertEqual(response.status_code, 200)

        draft_course.refresh_from_db()
        official_course.refresh_from_db()
        self.assertEqual(draft_course.short_description, updated_short_desc)
        self.assertEqual(official_course.short_description, updated_short_desc)
        self.assertEqual(draft_course.full_description, updated_full_desc)
        self.assertEqual(official_course.full_description, updated_full_desc)

        response = self.client.patch(url, {'prices': {'verified': 1000}, 'draft': False}, format='json')
        self.assertEqual(response.status_code, 200)

        draft_course.refresh_from_db()
        official_course.refresh_from_db()
        self.assertEqual(draft_course.entitlements.first().price, 1000)
        self.assertEqual(official_course.entitlements.first().price, 1000)

    def test_patch_publish_saves_old_url_in_history(self):
        self.mock_access_token()
        self.mock_ecommerce_publication()
        self.create_course_and_course_run()
        draft_course = Course.everything.last()
        draft_course_run = CourseRun.everything.last()
        draft_course_run.status = CourseRunStatus.Reviewed
        draft_course_run.save()
        draft_course_run.status = CourseRunStatus.Published
        draft_course_run.save()

        official_course = Course.everything.get(uuid=draft_course.uuid, draft=False)
        draft_course = official_course.draft_version

        self.assertEqual(official_course.active_url_slug, 'course-title')

        url = reverse('api:v1:course-detail', kwargs={'key': draft_course.uuid})

        response = self.client.patch(url, {'url_slug': 'manual', 'draft': False}, format='json')
        self.assertEqual(response.status_code, 200)

        draft_course.refresh_from_db()
        official_course.refresh_from_db()

        self.assertEqual(official_course.active_url_slug, 'manual')
        url_history = official_course.url_slug_history.all().values('url_slug')
        url_history_strings = [history_item['url_slug'] for history_item in url_history]
        self.assertIn('course-title', url_history_strings)

    def test_unpublished_url_slugs_not_added_to_history(self):
        self.mock_access_token()
        self.mock_ecommerce_publication()
        self.create_course_and_course_run()
        draft_course = Course.everything.last()
        draft_course_run = CourseRun.everything.last()
        draft_course_run.status = CourseRunStatus.Reviewed
        draft_course_run.save()
        draft_course_run.status = CourseRunStatus.Published
        draft_course_run.save()

        official_course = Course.everything.get(uuid=draft_course.uuid, draft=False)
        draft_course = official_course.draft_version

        self.assertEqual(official_course.active_url_slug, 'course-title')

        url = reverse('api:v1:course-detail', kwargs={'key': draft_course.uuid})

        # add new slug to draft but don't publish
        response = self.client.patch(url, {'url_slug': 'unpublished', 'draft': True}, format='json')
        self.assertEqual(response.status_code, 200)

        draft_course.refresh_from_db()
        official_course.refresh_from_db()
        self.assertEqual(draft_course.active_url_slug, 'unpublished')
        self.assertEqual(official_course.active_url_slug, 'course-title')
        url_history = official_course.url_slug_history.all().values('url_slug')
        url_history_strings = [history_item['url_slug'] for history_item in url_history]
        self.assertNotIn('manual', url_history_strings)

        # add new slug and publish at the same time
        response = self.client.patch(url, {'url_slug': 'published', 'draft': False}, format='json')
        self.assertEqual(response.status_code, 200)
        official_course.refresh_from_db()
        self.assertEqual(official_course.active_url_slug, 'published')
        self.assertEqual(official_course.url_slug_history.count(), 2)

        # unpublished slug not in history, previously published slug is
        url_history = official_course.url_slug_history.all().values('url_slug')
        url_history_strings = [history_item['url_slug'] for history_item in url_history]
        self.assertNotIn('unpublished', url_history_strings)
        self.assertIn('course-title', url_history_strings)

        # unpublished slug is now available to other courses
        self.create_course({'url_slug': 'unpublished', 'number': 'a123'})
        new_course = Course.everything.last()
        self.assertEqual(new_course.active_url_slug, 'unpublished')

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

        self.assertEqual(CourseEntitlement.everything.count(), 0)

        # Republish with a verified slug
        url = reverse('api:v1:course-detail', kwargs={'key': draft_course.uuid})
        updates = {
            'type': str(CourseType.objects.get(slug=CourseType.VERIFIED_AUDIT).uuid),
            'prices': {
                'verified': 1000,
            },
            'draft': False,
        }
        response = self.client.patch(url, updates, format='json')
        self.assertEqual(response.status_code, 200)

        draft_course.refresh_from_db()
        official_course.refresh_from_db()
        self.assertEqual(CourseEntitlement.everything.count(), 2)
        self.assertEqual(draft_course.entitlements.first().price, 1000)
        self.assertEqual(draft_course.entitlements.first().mode.slug, Seat.VERIFIED)
        self.assertEqual(official_course.entitlements.first().price, 1000)
        self.assertEqual(official_course.entitlements.first().mode.slug, Seat.VERIFIED)

    @responses.activate
    def test_patch_draft_switch_verified_to_audit(self):
        """
        Verify that draft rows can be updated from a "Verified and Audit" Course with
        a Verified Entitlement to an "Audit Only" course with no entitlements
        """
        self.mock_access_token()
        self.mock_ecommerce_publication()
        data = {'type': str(CourseType.objects.get(slug=CourseType.VERIFIED_AUDIT).uuid)}
        self.create_course_and_course_run(data)

        draft_course = Course.everything.last()

        self.assertEqual(CourseEntitlement.everything.count(), 1)

        url = reverse('api:v1:course-detail', kwargs={'key': draft_course.uuid})
        updates = {
            'type': str(CourseType.objects.get(slug=CourseType.AUDIT).uuid),
        }
        response = self.client.patch(url, updates, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(CourseEntitlement.everything.count(), 0)

    @responses.activate
    def test_patch_creates_draft_entitlement_if_possible(self):
        """
        If an official course exists and does not have an entitlement, during the ensure_draft_world call,
        we attempt to create an entitlement based on the seat data from the course runs. As long as all seat
        data from active course runs (see Course.active_course_runs) match, we will create an entitlement.
        """
        self.mock_access_token()
        future = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=10)
        run = CourseRunFactory(course=self.course, end=future, enrollment_end=None)
        seat = SeatFactory(course_run=run, type=SeatTypeFactory.verified())
        self.assertFalse(Course.everything.filter(uuid=self.course.uuid, draft=True).exists())  # sanity check
        self.assertIsNone(self.course.entitlements.first())

        url = reverse('api:v1:course-detail', kwargs={'key': self.course.uuid})
        response = self.client.patch(url, {'title': 'Title'}, format='json')
        self.assertEqual(response.status_code, 200)

        course = Course.everything.get(uuid=self.course.uuid, draft=True)

        self.assertEqual(course.entitlements.count(), 1)
        entitlement = course.entitlements.first()
        self.assertEqual(entitlement.mode.slug, Seat.VERIFIED)
        self.assertEqual(entitlement.price, seat.price)
        self.assertEqual(entitlement.currency, seat.currency)
        self.assertTrue(entitlement.draft)

        # The official version of the course should still not have any entitlements
        self.assertIsNone(self.course.entitlements.first())

    @ddt.unpack
    def test_cannot_change_type_after_review(self):
        url = reverse('api:v1:course-detail', kwargs={'key': self.course.uuid})
        response = self.client.patch(url, {
            'type': str(CourseType.objects.get(slug=CourseType.PROFESSIONAL).uuid),
            'prices': {
                Seat.PROFESSIONAL: 1000,
            },
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            'Switching entitlement types after being reviewed is not supported. Please reach out to your ' +
            'project coordinator for additional help if necessary.'
        )

    def test_update_fails_if_manual_slug_exists(self):
        self.mock_access_token()
        response = self.create_course()
        self.assertEqual(response.status_code, 201)
        course = Course.everything.last()
        self.assertEqual(course.active_url_slug, 'course-title')

        course_data = {'url_slug': 'course-title'}
        url = reverse('api:v1:course-detail', kwargs={'key': self.course.key})
        response = self.client.patch(url, course_data, format='json')
        self.assertEqual(response.status_code, 400)
        expected_error_message = 'Failed to set data: Course edit was unsuccessful. ' \
                                 'The course URL slug ‘[course-title]’ is already in use. ' \
                                 'Please update this field and try again.'
        self.assertEqual(response.data, expected_error_message)

    def test_update_fails_if_manual_slug_in_other_course_history(self):
        self.mock_access_token()
        self.mock_ecommerce_publication()
        self.create_course_and_course_run()
        draft_course = Course.everything.last()
        draft_course_run = CourseRun.everything.last()
        draft_course_run.status = CourseRunStatus.Reviewed
        draft_course_run.save()
        draft_course_run.status = CourseRunStatus.Published
        draft_course_run.save()

        official_course = Course.everything.get(uuid=draft_course.uuid, draft=False)
        draft_course = official_course.draft_version

        self.assertEqual(official_course.active_url_slug, 'course-title')

        url = reverse('api:v1:course-detail', kwargs={'key': draft_course.uuid})

        response = self.client.patch(url, {'url_slug': 'manual', 'draft': False}, format='json')
        self.assertEqual(response.status_code, 200)

        # at this point history of the created course should contain 'course-title'
        course_data = {'url_slug': 'course-title'}
        url = reverse('api:v1:course-detail', kwargs={'key': self.course.key})
        response = self.client.patch(url, course_data, format='json')
        self.assertEqual(response.status_code, 400)
        expected_error_message = 'Failed to set data: Course edit was unsuccessful. ' \
                                 'The course URL slug ‘[course-title]’ is already in use. ' \
                                 'Please update this field and try again.'
        self.assertEqual(response.data, expected_error_message)

    def test_update_succeeds_if_reusing_previous_slug_on_same_course(self):
        self.mock_access_token()
        self.mock_ecommerce_publication()
        self.create_course_and_course_run()
        draft_course = Course.everything.last()
        draft_course_run = CourseRun.everything.last()
        draft_course_run.status = CourseRunStatus.Reviewed
        draft_course_run.save()
        draft_course_run.status = CourseRunStatus.Published
        draft_course_run.save()

        official_course = Course.everything.get(uuid=draft_course.uuid, draft=False)
        draft_course = official_course.draft_version

        self.assertEqual(official_course.active_url_slug, 'course-title')

        url = reverse('api:v1:course-detail', kwargs={'key': draft_course.uuid})

        response = self.client.patch(url, {'url_slug': 'manual', 'draft': False}, format='json')
        self.assertEqual(response.status_code, 200)
        draft_course.refresh_from_db()
        self.assertEqual(draft_course.active_url_slug, 'manual')

        # at this point history of the created course should contain 'course-title'
        course_data = {'url_slug': 'course-title'}
        url = reverse('api:v1:course-detail', kwargs={'key': draft_course.uuid})
        response = self.client.patch(url, course_data, format='json')
        self.assertEqual(response.status_code, 200)
        draft_course.refresh_from_db()
        self.assertEqual(draft_course.active_url_slug, 'course-title')

    def test_update_with_api_exception(self):
        url = reverse('api:v1:course-detail', kwargs={'key': self.course.uuid})
        course_data = {
            'title': 'Course title',
            'type': str(self.verified_type.uuid),
            'prices': {
                'verified': 1000,
            },
        }

        with mock.patch(
            'course_discovery.apps.api.v1.views.courses.CourseViewSet.update_entitlement',
            side_effect=IntegrityError('Nope')
        ):
            with LogCapture(course_logger.name) as log_capture:
                response = self.client.patch(url, course_data, format='json')
                self.assertEqual(response.status_code, 400)
                log_capture.check_present(
                    (
                        course_logger.name,
                        'ERROR',
                        'Failed to set data: Nope',
                    )
                )

    def test_update_fails_with_nonexistent_course_type(self):
        url = reverse('api:v1:course-detail', kwargs={'key': self.course.uuid})

        with LogCapture(course_logger.name) as log_capture:
            response = self.client.patch(url, {'type': '00000000-0000-0000-0000-000000000000'}, format='json')
            self.assertEqual(response.status_code, 400)
            log_capture.check_present(
                (
                    course_logger.name,
                    'ERROR',
                    ("Failed to set data: {'type': [ErrorDetail(string='Object with "
                     "uuid=00000000-0000-0000-0000-000000000000 does not exist.', code='does_not_exist')]}"),
                )
            )

    @responses.activate
    def test_options(self):
        self.mock_access_token()
        SubjectFactory(name='Subject1')
        CourseEntitlementFactory(course=self.course, mode=SeatTypeFactory.verified())

        url = reverse('api:v1:course-detail', kwargs={'key': self.course.uuid})
        with self.assertNumQueries(40, threshold=0):
            response = self.client.options(url)
        self.assertEqual(response.status_code, 200)

        data = response.json()['actions']['PUT']
        self.assertEqual(data['level_type']['choices'],
                         [{'display_name': self.course.level_type.name_t, 'value': self.course.level_type.name_t}])
        self.assertEqual(data['entitlements']['child']['children']['mode']['choices'],
                         [{'display_name': 'Audit', 'value': 'audit'},
                          {'display_name': 'Credit', 'value': 'credit'},
                          {'display_name': 'Honor', 'value': 'honor'},
                          {'display_name': 'Professional', 'value': 'professional'},
                          {'display_name': 'Verified', 'value': 'verified'}])
        self.assertEqual(data['subjects']['child']['choices'],
                         [{'display_name': 'Subject1', 'value': 'subject1'}])
        self.assertNotIn('choices', data['partner'])  # we don't whitelist partner to show its choices

        # Check that tracks come out alright
        credit_type = CourseType.objects.get(slug=CourseType.CREDIT_VERIFIED_AUDIT)
        credit_options = None
        for options in data['type']['type_options']:
            if options['uuid'] == str(credit_type.uuid):
                credit_options = options
                break
        self.assertIsNotNone(credit_options)
        self.assertEqual({t['mode']['slug'] for t in credit_options['tracks']},
                         {'verified', 'credit', 'audit'})

    @responses.activate
    @ddt.data(True, False)
    def test_retrieve_will_create_entitlement(self, has_entitlement):
        """ When retrieving a course, test that an entitlement gets created if needed """
        self.mock_access_token()

        self.assertFalse(self.course.entitlements.exists())  # sanity check

        run = CourseRunFactory(course=self.course)
        SeatFactory(type=SeatTypeFactory.verified(), course_run=run, price=40)
        if has_entitlement:
            CourseEntitlementFactory(course=self.course, price=40, mode=SeatTypeFactory.verified())

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

    @responses.activate
    def test_html_stripped(self):
        self.mock_access_token()
        url = reverse('api:v1:course-detail', kwargs={'key': self.course.uuid})
        response = self.client.patch(url, {'full_description': '<p class="test">Desc</p>'}, format='json')
        self.assertEqual(response.status_code, 200)
        draft = Course.everything.get(uuid=self.course.uuid, draft=True)
        self.assertEqual(draft.full_description, '<p>Desc</p>')

    @responses.activate
    def test_html_restricted(self):
        self.mock_access_token()
        url = reverse('api:v1:course-detail', kwargs={'key': self.course.uuid})
        response = self.client.patch(url, {'full_description': '<h1>Header</h1>'}, format='json')
        self.assertContains(response, 'Invalid HTML received: h1 tag is not allowed', status_code=400)
