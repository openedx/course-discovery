import datetime
import urllib
from unittest import mock

import ddt
import pytest
import pytz
import responses
from django.contrib.auth.models import Group
from django.db.models.functions import Lower
from rest_framework.reverse import reverse
from rest_framework.test import APIRequestFactory

from course_discovery.apps.api.v1.exceptions import EditableAndQUnsupported
from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase, OAuth2Mixin, SerializationMixin
from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.core.tests.mixins import ElasticsearchTestMixin
from course_discovery.apps.course_metadata.choices import CourseRunStatus, ProgramStatus
from course_discovery.apps.course_metadata.models import CourseRun, CourseRunType, Seat, SeatType
from course_discovery.apps.course_metadata.tests.factories import (
    CourseEditorFactory, CourseFactory, CourseRunFactory, CourseRunTypeFactory, CourseTypeFactory, OrganizationFactory,
    PersonFactory, ProgramFactory, SeatFactory, TrackFactory
)
from course_discovery.apps.ietf_language_tags.models import LanguageTag
from course_discovery.apps.publisher.tests.factories import OrganizationExtensionFactory


@ddt.ddt
class CourseRunViewSetTests(SerializationMixin, ElasticsearchTestMixin, OAuth2Mixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.user = UserFactory(is_staff=True)
        self.client.force_authenticate(self.user)
        self.course_run = CourseRunFactory(course__partner=self.partner)
        self.course_run_2 = CourseRunFactory(course__key='Test+Course', course__partner=self.partner)
        self.draft_course = CourseFactory(partner=self.partner, draft=True)
        self.draft_course_run = CourseRunFactory(course=self.draft_course, draft=True)
        self.draft_course_run.course.authoring_organizations.add(OrganizationFactory(key='course-id'))
        self.course_run_type = CourseRunTypeFactory(tracks=[TrackFactory()])
        self.verified_type = CourseRunType.objects.get(slug=CourseRunType.VERIFIED_AUDIT)
        self.refresh_index()
        self.request = APIRequestFactory().get('/')
        self.request.user = self.user
        self.partner.lms_url = 'http://127.0.0.1:8000'
        self.partner.save()

    def mock_patch_to_studio(self, key, access_token=True, status=200, body=None):
        if access_token:
            self.mock_access_token()
        studio_url = '{root}/api/v1/course_runs/{key}/'.format(root=self.partner.studio_url.strip('/'), key=key)
        responses.add(responses.PATCH, studio_url, status=status, body=body)
        responses.add(responses.POST, f'{studio_url}images/', status=status, body=body)

    def mock_post_to_studio(self, key, access_token=True, rerun_key=None):
        if access_token:
            self.mock_access_token()
        studio_url = '{root}/api/v1/course_runs/'.format(root=self.partner.studio_url.strip('/'))
        if rerun_key:
            responses.add(responses.POST, f'{studio_url}{rerun_key}/rerun/', status=200)
        else:
            responses.add(responses.POST, studio_url, status=200)
        responses.add(responses.POST, f'{studio_url}{key}/images/', status=200)

    def mock_ecommerce_publication(self):
        url = f'{self.partner.ecommerce_api_url}publication/'
        responses.add(responses.POST, url, json={}, status=200)

    def test_get(self):
        """ Verify the endpoint returns the details for a single course. """
        url = reverse('api:v1:course_run-detail', kwargs={'key': self.course_run.key})

        with self.assertNumQueries(11):
            response = self.client.get(url)

        assert response.status_code == 200
        self.assertEqual(response.data, self.serialize_course_run(self.course_run))

    def test_get_exclude_deleted_programs(self):
        """ Verify the endpoint returns no associated deleted programs """
        ProgramFactory(courses=[self.course_run.course], status=ProgramStatus.Deleted)

        url = reverse('api:v1:course_run-detail', kwargs={'key': self.course_run.key})

        with self.assertNumQueries(12):
            response = self.client.get(url)
        assert response.status_code == 200
        assert response.data.get('programs') == []

    def test_get_include_deleted_programs(self):
        """
        Verify the endpoint returns associated deleted programs
        with the 'include_deleted_programs' flag set to True
        """
        ProgramFactory(courses=[self.course_run.course], status=ProgramStatus.Deleted)

        url = reverse('api:v1:course_run-detail', kwargs={'key': self.course_run.key})
        url += '?include_deleted_programs=1'

        with self.assertNumQueries(17):
            response = self.client.get(url)
        assert response.status_code == 200
        assert response.data == \
            self.serialize_course_run(self.course_run, extra_context={'include_deleted_programs': True})

    def test_get_exclude_unpublished_programs(self):
        """ Verify the endpoint returns no associated unpublished programs """
        ProgramFactory(courses=[self.course_run.course], status=ProgramStatus.Unpublished)

        url = reverse('api:v1:course_run-detail', kwargs={'key': self.course_run.key})

        with self.assertNumQueries(12):
            response = self.client.get(url)
            assert response.status_code == 200
            assert response.data.get('programs') == []

    def test_get_include_unpublished_programs(self):
        """
        Verify the endpoint returns associated unpublished programs
        with the 'include_unpublished_programs' flag set to True
        """
        ProgramFactory(courses=[self.course_run.course], status=ProgramStatus.Unpublished)

        url = reverse('api:v1:course_run-detail', kwargs={'key': self.course_run.key})
        url += '?include_unpublished_programs=1'

        with self.assertNumQueries(17):
            response = self.client.get(url)
        assert response.status_code == 200
        assert response.data == \
            self.serialize_course_run(self.course_run, extra_context={'include_unpublished_programs': True})

    @responses.activate
    def test_create_minimum(self):
        """ Verify the endpoint supports creating a course_run with the least info. """
        course = self.draft_course_run.course
        new_key = f'course-v1:{course.key_for_reruns}+1T2000'
        self.mock_post_to_studio(new_key)
        url = reverse('api:v1:course_run-list')

        # Send nothing - expect complaints
        response = self.client.post(url, {}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertDictEqual(response.data, {
            'course': ['This field is required.'],
        })

        # Send minimum requested
        response = self.client.post(url, {
            'course': course.key,
            'start': '2000-01-01T00:00:00Z',
            'end': '2001-01-01T00:00:00Z',
            'run_type': str(self.course_run_type.uuid),
        }, format='json')
        self.assertEqual(response.status_code, 201)
        new_course_run = CourseRun.everything.get(key=new_key)
        self.assertDictEqual(response.data, self.serialize_course_run(new_course_run))
        self.assertEqual(new_course_run.pacing_type, 'instructor_paced')  # default we provide
        self.assertEqual(str(new_course_run.end), '2001-01-01 00:00:00+00:00')  # spot check that input made it
        self.assertTrue(new_course_run.draft)

        new_seat = Seat.everything.get(course_run=new_course_run)
        self.assertEqual(new_seat.type, self.course_run_type.tracks.first().seat_type)
        self.assertEqual(new_seat.price, 0.00)
        self.assertTrue(new_seat.draft)

    @responses.activate
    def test_create_without_course_key_for_reruns(self):
        """ Verify the endpoint supports creating a course_run without a specified course key_for_reruns. """
        course = self.draft_course_run.course
        new_key = f'course-v1:{course.key_for_reruns}+1T2000'
        self.mock_post_to_studio(new_key)
        url = reverse('api:v1:course_run-list')

        data = {
            'course': course.key,
            'start': '2000-01-01T00:00:00Z',
            'end': '2001-01-01T00:00:00Z',
            'run_type': str(self.course_run_type.uuid),
        }

        self.assertNotEqual(course.key, course.key_for_reruns)  # sanity check

        # Try first with a boring old key_for_reruns
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['key'], new_key)
        CourseRun.everything.get(key=response.data['key'])

        # Now try without a key_for_reruns set
        course.key_for_reruns = ''
        course.save()
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['key'], 'course-v1:{}+1T2000'.format(course.key.replace('/', '+')))
        CourseRun.everything.get(key=response.data['key'])

    @ddt.data(True, False)
    @responses.activate
    def test_create_sets_canonical_course_run(self, has_canonical_run):
        """ Verify the endpoint supports setting an empty canonical course run. """
        course = self.draft_course_run.course
        new_key = f'course-v1:{course.key_for_reruns}+1T2000'
        url = reverse('api:v1:course_run-list')

        self.assertIsNone(course.canonical_course_run)  # sanity check
        if has_canonical_run:
            self.mock_post_to_studio(new_key, rerun_key=self.draft_course_run.key)
            course.canonical_course_run = self.draft_course_run
            course.save()
            rerun = self.draft_course_run.key
        else:
            self.mock_post_to_studio(new_key)
            rerun = None

        response = self.client.post(url, {
            'course': course.key,
            'start': '2000-01-01T00:00:00Z',
            'end': '2001-01-01T00:00:00Z',
            'run_type': str(self.course_run_type.uuid),
            'rerun': rerun,
        }, format='json')

        self.assertEqual(response.status_code, 201)
        new_course_run = CourseRun.everything.get(key=new_key)

        course.refresh_from_db()
        if has_canonical_run:
            # Shouldn't change existing canonical course run
            self.assertEqual(course.canonical_course_run, self.draft_course_run)
        else:
            self.assertEqual(course.canonical_course_run, new_course_run)

    @responses.activate
    def test_create_sets_additional_fields(self):
        """ Verify that instructors, languages, min & max effort, and weeks to complete are set on a rerun. """
        self.draft_course_run.staff.add(PersonFactory())
        self.draft_course_run.transcript_languages.add(self.draft_course_run.language)
        self.draft_course_run.save()

        # Create rerun based on draft course
        course = self.draft_course_run.course
        new_key = f'course-v1:{course.key_for_reruns}+1T2000'
        url = reverse('api:v1:course_run-list')

        self.mock_post_to_studio(new_key, rerun_key=self.draft_course_run.key)

        response = self.client.post(url, {
            'course': course.key,
            'start': '2000-01-01T00:00:00Z',
            'end': '2001-01-01T00:00:00Z',
            'run_type': str(self.course_run_type.uuid),
            'rerun': self.draft_course_run.key,
        }, format='json')

        self.assertEqual(response.status_code, 201)
        new_course_run = CourseRun.everything.get(key=new_key, draft=True)

        self.assertEqual(new_course_run.max_effort, self.draft_course_run.max_effort)
        self.assertEqual(new_course_run.min_effort, self.draft_course_run.min_effort)
        self.assertEqual(new_course_run.weeks_to_complete, self.draft_course_run.weeks_to_complete)
        self.assertEqual(list(new_course_run.staff.all()), list(self.draft_course_run.staff.all()))
        self.assertEqual(new_course_run.language, self.draft_course_run.language)
        self.assertEqual(list(new_course_run.transcript_languages.all()),
                         list(self.draft_course_run.transcript_languages.all()))

    @ddt.data(True, False, "bogus")
    @responses.activate
    def test_create_draft_ignored(self, draft):
        """ Verify the endpoint supports creating a course_run, but always as a draft. """
        course = self.draft_course_run.course
        new_key = f'course-v1:{course.key_for_reruns}+1T2000'
        self.mock_post_to_studio(new_key)
        url = reverse('api:v1:course_run-list')

        # Send minimum + draft: True/False/bogus
        response = self.client.post(url, {
            'course': course.key,
            'start': '2000-01-01T00:00:00Z',
            'end': '2001-01-01T00:00:00Z',
            'run_type': str(self.course_run_type.uuid),
            'draft': draft,
        }, format='json')

        self.assertEqual(response.status_code, 201)
        new_course_run = CourseRun.everything.get(key=new_key)
        self.assertDictEqual(response.data, self.serialize_course_run(new_course_run))
        self.assertTrue(new_course_run.draft)

    @responses.activate
    def test_create_using_type_with_price(self):
        """ Verify the endpoint supports creating a course_run and sets the seats price to the given price """
        course = self.draft_course_run.course
        new_key = f'course-v1:{course.key_for_reruns}+1T2000'
        self.mock_post_to_studio(new_key)
        url = reverse('api:v1:course_run-list')

        response = self.client.post(url, {
            'course': course.key,
            'start': '2000-01-01T00:00:00Z',
            'end': '2001-01-01T00:00:00Z',
            'run_type': str(self.course_run_type.uuid),
            'prices': {self.course_run_type.tracks.first().seat_type.slug: 77.32},
        }, format='json')

        self.assertEqual(response.status_code, 201)
        new_course_run = CourseRun.everything.get(key=new_key)
        self.assertDictEqual(response.data, self.serialize_course_run(new_course_run))
        self.assertTrue(new_course_run.draft)

        new_seat = Seat.everything.get(course_run=new_course_run)
        self.assertEqual(new_seat.type, self.course_run_type.tracks.first().seat_type)
        self.assertEqual(float(new_seat.price), 77.32)
        self.assertTrue(new_seat.draft)

    @responses.activate
    def test_create_using_type_with_no_track_seat_types(self):
        """
        Verify the endpoint supports creating a course_run with no seats
        There will be no seats if the run_type has only Tracks with no seat types defined
        """
        course = self.draft_course_run.course
        new_key = f'course-v1:{course.key_for_reruns}+1T2000'
        self.mock_post_to_studio(new_key)
        url = reverse('api:v1:course_run-list')
        run_type = CourseRunTypeFactory(tracks=[TrackFactory(seat_type=None)])

        response = self.client.post(url, {
            'course': course.key,
            'start': '2000-01-01T00:00:00Z',
            'end': '2001-01-01T00:00:00Z',
            'run_type': str(run_type.uuid),
        }, format='json')

        self.assertEqual(response.status_code, 201)
        new_course_run = CourseRun.everything.get(key=new_key)
        self.assertDictEqual(response.data, self.serialize_course_run(new_course_run))
        self.assertTrue(new_course_run.draft)

        self.assertEqual(Seat.everything.filter(course_run=new_course_run).count(), 0)

    @responses.activate
    def test_create_with_term(self):
        """ Verify the endpoint supports creating a course_run when specifying a key (if allowed). """
        course = self.draft_course_run.course
        date_key = f'course-v1:{course.key_for_reruns}+1T2000'
        desired_term = 'HowdyDoing'
        url = reverse('api:v1:course_run-list')

        data = {
            'course': course.key,
            'start': '2000-01-01T00:00:00Z',
            'end': '2001-01-01T00:00:00Z',
            'run_type': str(self.course_run_type.uuid),
            'term': desired_term,
        }

        # If org doesn't specifically allow it, incoming key is ignored
        self.mock_post_to_studio(date_key)
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 201)
        new_course_run = CourseRun.everything.get(key=date_key)
        self.assertDictEqual(response.data, self.serialize_course_run(new_course_run))

        # Turn on this feature for this org, notice that we can now specify the course key we want
        org_ext = OrganizationExtensionFactory(organization=course.authoring_organizations.first())
        org_ext.organization.auto_generate_course_run_keys = False
        org_ext.organization.save()
        self.mock_post_to_studio(desired_term, access_token=False, rerun_key=new_course_run.key)
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 201)
        new_course_run = CourseRun.everything.get(key=f'course-v1:{course.key_for_reruns}+{desired_term}')
        self.assertDictEqual(response.data, self.serialize_course_run(new_course_run))

    def test_create_if_in_org(self):
        """ Verify the endpoint supports creating a course_run with organization permissions. """
        url = reverse('api:v1:course_run-list')
        course = self.draft_course_run.course
        data = {'course': course.key}

        self.user.is_staff = False
        self.user.save()

        # Not in org, not allowed to POST
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 403)

        # Add to org
        org_ext = OrganizationExtensionFactory(organization=course.authoring_organizations.first())
        self.user.groups.add(org_ext.group)

        # now allowed to POST
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 400)  # missing start, but at least we got that far

    def test_create_fails_with_all_missing_fields(self):
        course = self.draft_course_run.course
        new_key = f'course-v1:{course.key_for_reruns}+1T2000'
        self.mock_post_to_studio(new_key)
        url = reverse('api:v1:course_run-list')

        # Send nothing - expect missing course complaint
        response = self.client.post(url, {}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertDictEqual(response.data, {
            'course': ['This field is required.'],
        })

    def test_create_fails_with_partial_missing_fields(self):
        course = self.draft_course_run.course
        new_key = f'course-v1:{course.key_for_reruns}+1T2000'
        self.mock_post_to_studio(new_key)
        url = reverse('api:v1:course_run-list')

        data = {
            'course': course.key,
        }

        # Send just course key - expect complaints
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertDictEqual(response.data, {
            'start': ['This field is required.'],
            'end': ['This field is required.'],
            'run_type': ['This field is required.'],
        })

    @responses.activate
    def test_create_succeeds_with_failed_image_update_to_studio(self):
        course = self.draft_course_run.course
        course.canonical_course_run = self.draft_course_run
        course.save()
        new_key = f'course-v1:{course.key_for_reruns}+1T2000'
        url = reverse('api:v1:course_run-list')

        self.mock_access_token()
        studio_url = '{root}/api/v1/course_runs/'.format(root=self.partner.studio_url.strip('/'))
        responses.add(responses.POST, f'{studio_url}{self.draft_course_run.key}/rerun/')
        responses.add(responses.POST, f'{studio_url}{new_key}/images/', status=400)

        with mock.patch('course_discovery.apps.api.utils.logger.exception') as mock_logger:
            response = self.client.post(url, {
                'course': course.key,
                'start': '2000-01-01T00:00:00Z',
                'end': '2001-01-01T00:00:00Z',
                'run_type': str(self.course_run_type.uuid),
                'rerun': self.draft_course_run.key,
            }, format='json')
        self.assertEqual(response.status_code, 201)

        self.assertEqual(mock_logger.call_count, 1)
        self.assertEqual(mock_logger.call_args_list[0], mock.call(
            'An error occurred while setting the course run image for [{key}] in studio. All other fields '
            'were successfully saved in Studio.'.format(key=new_key)
        ))

    @responses.activate
    def test_update_operates_on_drafts(self):
        self.assertFalse(CourseRun.everything.filter(key=self.course_run.key, draft=True).exists())  # sanity check
        self.mock_patch_to_studio(self.course_run.key)
        expected_original_max_effort = self.course_run.max_effort

        url = reverse('api:v1:course_run-detail', kwargs={'key': self.course_run.key})
        response = self.client.patch(url, {'max_effort': 777}, format='json')
        self.assertEqual(response.status_code, 200)

        course_run = CourseRun.everything.get(key=self.course_run.key, draft=True)
        self.assertEqual(course_run.max_effort, 777)

        self.course_run.refresh_from_db()
        self.assertFalse(self.course_run.draft)
        self.assertEqual(self.course_run.max_effort, expected_original_max_effort)

    @responses.activate
    def test_partial_update(self):
        """ Verify the endpoint supports partially updating a course_run's fields, provided user has permission. """
        self.mock_patch_to_studio(self.draft_course_run.key)

        url = reverse('api:v1:course_run-detail', kwargs={'key': self.draft_course_run.key})

        expected_min_effort = 867
        expected_max_effort = 5309
        data = {
            'max_effort': expected_max_effort,
            'min_effort': expected_min_effort,
        }

        # Update this course_run with the new info
        response = self.client.patch(url, data, format='json')
        assert response.status_code == 200

        # refresh and make sure we have the new effort levels
        self.draft_course_run.refresh_from_db()

        assert self.draft_course_run.max_effort == expected_max_effort
        assert self.draft_course_run.min_effort == expected_min_effort

    def test_partial_update_no_studio_url(self):
        """ Verify we skip pushing when no studio url is set. """
        orignal_partner_studio_url = self.partner.studio_url
        self.partner.studio_url = None
        self.partner.save()

        url = reverse('api:v1:course_run-detail', kwargs={'key': self.draft_course_run.key})

        with mock.patch('course_discovery.apps.api.v1.views.course_runs.log.info') as mock_logger:
            # Just pick any date that will be ahead of the ones in the Factory
            response = self.client.patch(url, {'start': '2019-01-01T00:00:00Z'}, format='json')

        self.assertEqual(response.status_code, 200, f"Status {response.status_code}: {response.content}")

        self.assertIn(mock.call(
            'Not pushing course run info for %s to Studio as partner %s has no studio_url set.',
            self.draft_course_run.key,
            self.partner.short_code,
        ), mock_logger.call_args_list)

        self.assertIn(mock.call(
            'Not updating course run image for %s to Studio as partner %s has no studio_url set.',
            self.draft_course_run.key,
            self.partner.short_code,
        ), mock_logger.call_args_list)

        # reset the shared self.partner attribute
        self.partner.studio_url = orignal_partner_studio_url
        self.partner.save()

    def test_partial_update_bad_permission(self):
        """ Verify partially updating will fail if user doesn't have permission. """
        user = UserFactory(is_staff=False, is_superuser=False)
        self.client.force_authenticate(user)
        url = reverse('api:v1:course_run-detail', kwargs={'key': self.draft_course_run.key})
        response = self.client.patch(url, {}, format='json')
        assert response.status_code == 403

    @ddt.data(
        (
            {'start': '2010-01-01T00:00:00Z', 'end': '2000-01-01T00:00:00Z'},
            'Start date cannot be after the End date',
        ),
        (
            {'term': 'BlargHello'},
            'Term cannot be changed',
        ),
        (
            {'course': 'Test+Course'},
            'Course cannot be changed',
        ),
        (
            {'min_effort': 10000},
            'Minimum effort cannot be greater than Maximum effort',
        ),
        (
            {'min_effort': 10000, 'max_effort': 10000},
            'Minimum effort and Maximum effort cannot be the same',
        ),
    )
    @ddt.unpack
    def test_partial_update_common_errors(self, data, error):
        """ Verify partially updating will fail depending on various validation checks. """
        url = reverse('api:v1:course_run-detail', kwargs={'key': self.draft_course_run.key})
        response = self.client.patch(url, data, format='json')
        self.assertContains(response, error, status_code=400)

    def test_partial_update_staff(self):
        """ Verify partially updating allows staff updates. """
        self.mock_patch_to_studio(self.draft_course_run.key)

        p1 = PersonFactory()
        p2 = PersonFactory()
        PersonFactory()

        url = reverse('api:v1:course_run-detail', kwargs={'key': self.draft_course_run.key})
        response = self.client.patch(url, {'staff': [p2.uuid, p1.uuid]}, format='json')
        self.assertEqual(response.status_code, 200)

        self.draft_course_run.refresh_from_db()
        self.assertListEqual(list(self.draft_course_run.staff.all()), [p2, p1])

    @responses.activate
    def test_partial_update_video(self):
        """ Verify partially updating allows video updates. """
        self.mock_patch_to_studio(self.draft_course_run.key)

        url = reverse('api:v1:course_run-detail', kwargs={'key': self.draft_course_run.key})
        response = self.client.patch(url, {'video': {'src': 'https://example.com/blarg'}}, format='json')
        self.assertEqual(response.status_code, 200)

        self.draft_course_run.refresh_from_db()
        self.assertEqual(self.draft_course_run.video.src, 'https://example.com/blarg')

    @responses.activate
    def test_update_if_editor(self):
        """ Verify the endpoint supports updating a course_run with editor permissions. """
        self.mock_patch_to_studio(self.draft_course_run.key)
        url = reverse('api:v1:course_run-detail', kwargs={'key': self.draft_course_run.key})

        self.user.is_staff = False
        self.user.save()

        # Not an editor, not allowed to patch
        response = self.client.patch(url, {}, format='json')
        self.assertEqual(response.status_code, 403)

        # Add as editor
        org_ext = OrganizationExtensionFactory(
            organization=self.draft_course_run.course.authoring_organizations.first()
        )
        self.user.groups.add(org_ext.group)
        CourseEditorFactory(user=self.user, course=self.draft_course_run.course)

        # now allowed to patch
        response = self.client.patch(url, {}, format='json')
        self.assertEqual(response.status_code, 200)

    @responses.activate
    def test_studio_update_failure(self):
        """ Verify we bubble up error correctly if studio is giving us static. """
        self.mock_patch_to_studio(self.draft_course_run.key, status=400, body=b'Nope')

        url = reverse('api:v1:course_run-detail', kwargs={'key': self.draft_course_run.key})
        response = self.client.patch(url, {'title': 'New Title'}, format='json')
        self.assertContains(response, 'Failed to set course run data: Nope', status_code=400)

        self.draft_course_run.refresh_from_db()
        self.assertEqual(self.draft_course_run.title_override, None)  # prove we didn't touch the course run object

    @responses.activate
    def test_full_update(self):
        """ Verify full updating is allowed. """
        self.mock_patch_to_studio(self.draft_course_run.key)

        url = reverse('api:v1:course_run-detail', kwargs={'key': self.draft_course_run.key})
        response = self.client.put(url, {
            'course': self.draft_course_run.course.key,  # required, so we need for a put
            'start': self.draft_course_run.start,  # required, so we need for a put
            'end': self.draft_course_run.end,  # required, so we need for a put
            'run_type': str(self.draft_course_run.type.uuid),  # required, so we need for a put
            'title': 'New Title',
        }, format='json')
        assert response.status_code == 200, f"Status {response.status_code}: {response.content}"

        self.draft_course_run.refresh_from_db()
        self.assertEqual(self.draft_course_run.title_override, 'New Title')

    @ddt.data(
        CourseRunStatus.LegalReview,
        CourseRunStatus.InternalReview,
    )
    def test_patch_put_restrict_when_reviewing(self, status):
        self.draft_course_run.status = status
        self.draft_course_run.save()
        url = reverse('api:v1:course_run-detail', kwargs={'key': self.draft_course_run.key})
        response = self.client.put(url, {
            'course': self.draft_course_run.course.key,  # required, so we need for a put
            'start': self.draft_course_run.start,  # required, so we need for a put
            'end': self.draft_course_run.end,  # required, so we need for a put
            'run_type': str(self.draft_course_run.type.uuid),  # required, so we need for a put
        }, format='json')
        assert response.status_code == 403

        response = self.client.patch(url, {}, format='json')
        assert response.status_code == 403

    @responses.activate
    def test_patch_put_does_not_change_status(self):
        self.mock_patch_to_studio(self.draft_course_run.key)
        self.mock_ecommerce_publication()
        self.draft_course_run.status = CourseRunStatus.Reviewed
        self.draft_course_run.save()
        official_course_run = CourseRun.everything.get(key=self.draft_course_run.key, draft=False)
        assert official_course_run.status == CourseRunStatus.Reviewed

        url = reverse('api:v1:course_run-detail', kwargs={'key': self.draft_course_run.key})
        response = self.client.put(url, {
            'course': self.draft_course_run.course.key,  # required, so we need for a put
            'start': self.draft_course_run.start,  # required, so we need for a put
            'end': self.draft_course_run.end,  # required, so we need for a put
            'run_type': str(self.draft_course_run.type.uuid),  # required, so we need for a put
        }, format='json')
        assert response.status_code == 200, f"Status {response.status_code}: {response.content}"
        self.draft_course_run.refresh_from_db()
        draft_course_run = CourseRun.everything.get(key=self.draft_course_run.key, draft=True)
        assert draft_course_run.status == CourseRunStatus.Reviewed
        assert draft_course_run.official_version.status == CourseRunStatus.Reviewed

    @responses.activate
    def test_patch_put_reset_status(self):
        self.mock_patch_to_studio(self.draft_course_run.key)
        self.mock_ecommerce_publication()
        self.draft_course_run.status = CourseRunStatus.Reviewed
        self.draft_course_run.save()
        official_course_run = CourseRun.everything.get(key=self.draft_course_run.key, draft=False)
        assert official_course_run.status == CourseRunStatus.Reviewed

        url = reverse('api:v1:course_run-detail', kwargs={'key': self.draft_course_run.key})
        response = self.client.put(url, {
            'course': self.draft_course_run.course.key,  # required, so we need for a put
            'start': self.draft_course_run.start,  # required, so we need for a put
            'end': self.draft_course_run.end,  # required, so we need for a put
            'run_type': str(self.draft_course_run.type.uuid),  # required, so we need for a put
            'full_description': 'Some new description',  # required to cause a diff to update status
        }, format='json')
        assert response.status_code == 200, f"Status {response.status_code}: {response.content}"
        self.draft_course_run.refresh_from_db()
        draft_course_run = CourseRun.everything.get(key=self.draft_course_run.key, draft=True)
        assert draft_course_run.status == CourseRunStatus.Unpublished
        assert draft_course_run.official_version.status == CourseRunStatus.Unpublished

    @responses.activate
    def test_patch_put_non_review_fields_does_not_reset_status(self):
        """
        Tests that exempt fields do not reset the draft and official course runs to
        the unpublished status. Also ensures that the official version is updated with
        the changes to the exempt fields.
        """
        self.mock_patch_to_studio(self.draft_course_run.key)
        self.mock_ecommerce_publication()
        self.draft_course_run.status = CourseRunStatus.Reviewed
        self.draft_course_run.go_live_date = datetime.datetime(2031, 1, 1, tzinfo=pytz.UTC)
        self.draft_course_run.save()
        official_course_run = CourseRun.everything.get(key=self.draft_course_run.key, draft=False)
        assert official_course_run.status == CourseRunStatus.Reviewed

        url = reverse('api:v1:course_run-detail', kwargs={'key': self.draft_course_run.key})
        # alter fields that do not require re-approval
        response = self.client.put(url, {
            'course': self.draft_course_run.course.key,  # required, so we need for a put
            'start': self.draft_course_run.start + datetime.timedelta(days=1),  # required, so we need for a put
            'end': self.draft_course_run.end + datetime.timedelta(days=1),  # required, so we need for a put
            'run_type': str(self.draft_course_run.type.uuid),  # required, so we need for a put
            'go_live_date': self.draft_course_run.go_live_date + datetime.timedelta(days=1),
            'min_effort': self.draft_course_run.min_effort + 1,
            'max_effort': self.draft_course_run.max_effort + 1,
            'weeks_to_complete': self.draft_course_run.weeks_to_complete + 1,
        }, format='json')
        assert response.status_code == 200, f"Status {response.status_code}: {response.content}"
        self.draft_course_run.refresh_from_db()
        draft_course_run = CourseRun.everything.get(key=self.draft_course_run.key, draft=True)
        assert draft_course_run.status == CourseRunStatus.Reviewed
        assert draft_course_run.official_version.status == CourseRunStatus.Reviewed
        assert draft_course_run.go_live_date == draft_course_run.official_version.go_live_date

    @ddt.data(
        ({
            'original_status': CourseRunStatus.Unpublished,
            'new_status': CourseRunStatus.LegalReview,
        }),
        ({
            'original_status': CourseRunStatus.Reviewed,
            'new_status': CourseRunStatus.Reviewed,
        }),
        ({
            'original_status': CourseRunStatus.Reviewed,
            'new_status': CourseRunStatus.LegalReview,
            'non_exempt_data': {
                'expected_program_name': 'example name',
            }
        }),
    )
    @responses.activate
    def test_patch_put_draft_false(self, update_transaction):
        """ Verify that setting draft to False moves status correctly. Test Cases: Unpublished Course Run,
        Reviewed Course Run, Reviewed Course Run Requiring Legal Review"""
        self.mock_patch_to_studio(self.draft_course_run.key)
        if update_transaction['original_status'] == CourseRunStatus.Reviewed:
            self.mock_ecommerce_publication()
        self.draft_course_run.status = update_transaction['original_status']
        self.draft_course_run.save()
        url = reverse('api:v1:course_run-detail', kwargs={'key': self.draft_course_run.key})
        body = {
            'course': self.draft_course_run.course.key,  # required, so we need for a put
            'start': self.draft_course_run.start,  # required, so we need for a put
            'end': self.draft_course_run.end,  # required, so we need for a put
            'run_type': str(self.draft_course_run.type.uuid),  # required, so we need for a put
            'draft': False,
        }
        if 'non_exempt_data' in update_transaction.keys():
            body.update(update_transaction['non_exempt_data'])
        response = self.client.put(url, body, format='json')
        assert response.status_code == 200, f"Status {response.status_code}: {response.content}"
        draft_course_run = CourseRun.everything.get(key=self.draft_course_run.key, draft=True)
        assert draft_course_run.status == update_transaction['new_status']

    @responses.activate
    def test_patch_published(self):
        """ Verify that draft rows can be updated and re-published with draft=False. """
        self.mock_patch_to_studio(self.draft_course_run.key)
        self.mock_ecommerce_publication()
        self.draft_course_run.min_effort = 0
        self.draft_course_run.max_effort = 1
        self.draft_course_run.status = CourseRunStatus.Reviewed  # Triggers creation of official versions
        self.draft_course_run.save()

        official_run = CourseRun.everything.get(key=self.draft_course_run.key, draft=False)
        draft_run = official_run.draft_version
        official_run.status = CourseRunStatus.Published
        draft_run.status = CourseRunStatus.Published
        official_run.save()
        draft_run.save()

        # Edit; should only touch draft
        url = reverse('api:v1:course_run-detail', kwargs={'key': self.draft_course_run.key})
        updated_min_effort = 867
        updated_max_effort = 5309
        data = {
            'max_effort': updated_max_effort,
            'min_effort': updated_min_effort,
        }
        response = self.client.patch(url, data, format='json')
        assert response.status_code == 200, f"Status {response.status_code}: {response.content}"

        draft_run.refresh_from_db()
        assert draft_run.status == CourseRunStatus.Published
        assert draft_run.min_effort == updated_min_effort
        assert draft_run.max_effort == updated_max_effort

        official_run.refresh_from_db()
        assert official_run.status == CourseRunStatus.Published
        assert official_run.min_effort != updated_min_effort
        assert official_run.max_effort != updated_max_effort

        # Re-publish; should update official with old and new changes.
        updated_end = datetime.datetime(2021, 1, 1, tzinfo=pytz.UTC)
        response = self.client.patch(url, {'end': updated_end, 'draft': False}, format='json')
        assert response.status_code == 200, f"Status {response.status_code}: {response.content}"

        official_run.refresh_from_db()
        draft_run.refresh_from_db()
        assert official_run.status == CourseRunStatus.Published
        assert official_run.min_effort == updated_min_effort
        assert official_run.max_effort == updated_max_effort
        assert draft_run.end == updated_end
        assert official_run.end == updated_end

    def create_course_and_run_types(self, seat_type):
        tracks = []
        entitlement_types = []
        if seat_type:
            entitlement_types.append(SeatType.objects.get(slug=seat_type))
            tracks.append(TrackFactory(seat_type=entitlement_types[0]))
        if seat_type == Seat.VERIFIED or not seat_type:
            audit_type_obj = SeatType.objects.get(slug=Seat.AUDIT)
            tracks.append(TrackFactory(seat_type=audit_type_obj))

        run_type = CourseRunTypeFactory(tracks=tracks)
        course_type = CourseTypeFactory(
            entitlement_types=entitlement_types,
            course_run_types=[run_type],
        )
        return course_type, run_type

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
    def test_patch_updating_seats_using_type(self, original_seat_type, seat_type, price):
        """
        Verify that draft seats are updated when the type being passed in changes.
        """
        # First create a course and course run using the original seat type to inform the
        # CourseType and CourseRunType
        original_course_type, original_run_type = self.create_course_and_run_types(original_seat_type)
        creation_data = {
            'title': 'Course title',
            'number': 'test101',
            'org': OrganizationFactory(key='test-key').key,
            'type': str(original_course_type.uuid),
            'prices': {} if original_seat_type == 'audit' else {original_seat_type: 49},
            'course_run': {
                'start': '2001-01-01T00:00:00Z',
                'end': datetime.datetime.now() + datetime.timedelta(days=1),
                'run_type': str(original_run_type.uuid),
            }
        }

        run_key = 'course-v1:{org}+{number}+1T2001'.format(org=creation_data['org'], number=creation_data['number'])
        self.mock_access_token()
        self.mock_post_to_studio(run_key)

        url = reverse('api:v1:course-list')
        response = self.client.post(url, creation_data, format='json')
        self.assertEqual(response.status_code, 201)

        self.mock_patch_to_studio(run_key)
        url = reverse('api:v1:course_run-detail', kwargs={'key': run_key})

        __, updated_run_type = self.create_course_and_run_types(seat_type)
        data = {
            'run_type': str(updated_run_type.uuid),
            'prices': {seat_type: price},
        }

        # Update this course_run with the new info
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, 200)

        draft_course_run = CourseRun.everything.last()
        num_seats = Seat.everything.count()
        if seat_type == 'verified':
            self.assertEqual(num_seats, 2)
            audit_seat = Seat.everything.get(course_run=draft_course_run, type__slug='audit')
            self.assertEqual(audit_seat.price, 0.00)
            self.assertTrue(audit_seat.draft)
        else:
            self.assertEqual(num_seats, 1)
        seat = Seat.everything.get(course_run=draft_course_run, type__slug=seat_type)
        self.assertEqual(seat.price, price)
        # This is probably not a great way of verifying this with the first, it just so happens
        # that if there are two tracks (verified and audit), the verified track is first
        self.assertEqual(seat.type, updated_run_type.tracks.first().seat_type)
        self.assertTrue(seat.draft)

    @responses.activate
    def test_patch_updating_seats_only_affects_active_course_runs_using_type(self):
        """
        Verify that draft seats are updated when the type being passed in changes.
        """
        # First create a course and course run using the original seat type to inform the
        # CourseType and CourseRunType
        course_type, run_type = self.create_course_and_run_types(Seat.VERIFIED)
        creation_data = {
            'title': 'Course title',
            'number': 'test101',
            'org': OrganizationFactory(key='test-key').key,
            'type': str(course_type.uuid),
            'prices': {Seat.VERIFIED: 49},
            'course_run': {
                'start': '2001-01-01T00:00:00Z',
                'end': datetime.datetime.now() + datetime.timedelta(days=-1),
                'run_type': str(run_type.uuid),
                'min_effort': 1,
            }
        }

        run_key = 'course-v1:{org}+{number}+1T2001'.format(org=creation_data['org'], number=creation_data['number'])
        self.mock_access_token()
        self.mock_post_to_studio(run_key)

        url = reverse('api:v1:course-list')
        response = self.client.post(url, creation_data, format='json')
        self.assertEqual(response.status_code, 201)

        draft_course_run = CourseRun.everything.last()
        self.assertEqual(draft_course_run.min_effort, 1)
        seat = Seat.everything.get(course_run=draft_course_run, type=Seat.VERIFIED)
        self.assertEqual(seat.price, 49)

        self.mock_patch_to_studio(run_key)
        url = reverse('api:v1:course_run-detail', kwargs={'key': run_key})

        # We are changing the min_effort on the archived run which is going to send the run_type
        # and an updated price along with it. The updated price should not go to this course run since it
        # is not active.
        data = {
            'min_effort': 5,
            'run_type': str(run_type.uuid),
            'prices': {Seat.VERIFIED: 77},
        }

        # Update this course_run with the new info
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, 200)

        draft_course_run.refresh_from_db()
        seat.refresh_from_db()
        # Min effort was still updated
        self.assertEqual(draft_course_run.min_effort, 5)
        # Price did not update to 49
        self.assertEqual(seat.price, 49)

    def test_list(self):
        """ Verify the endpoint returns a list of all course runs. """
        url = reverse('api:v1:course_run-list')

        with self.assertNumQueries(13):
            response = self.client.get(url)

        assert response.status_code == 200
        self.assertListEqual(
            response.data['results'],
            self.serialize_course_run(CourseRun.objects.all().order_by(Lower('key')), many=True)
        )

    def test_list_sorted_by_course_start_date(self):
        """ Verify the endpoint returns a list of all course runs sorted by start date. """
        url = '{root}?ordering=start'.format(root=reverse('api:v1:course_run-list'))

        with self.assertNumQueries(13):
            response = self.client.get(url)

        assert response.status_code == 200
        self.assertListEqual(
            response.data['results'],
            self.serialize_course_run(CourseRun.objects.all().order_by('start'), many=True)
        )

    def test_list_query(self):
        """ Verify the endpoint returns a filtered list of courses """
        course_runs = CourseRunFactory.create_batch(3, title='Some random title', course__partner=self.partner)
        CourseRunFactory(title='non-matching name')
        query = 'title:Some random title'
        url = '{root}?q={query}'.format(root=reverse('api:v1:course_run-list'), query=query)

        with self.assertNumQueries(42, threshold=2):
            response = self.client.get(url)

        actual_sorted = sorted(response.data['results'], key=lambda course_run: course_run['key'])
        expected_sorted = sorted(self.serialize_course_run(course_runs, many=True),
                                 key=lambda course_run: course_run['key'])
        self.assertListEqual(actual_sorted, expected_sorted)

    def assert_list_results(self, url, expected, extra_context=None):
        expected = sorted(expected, key=lambda course_run: course_run.key.lower())
        response = self.client.get(url)
        assert response.status_code == 200
        self.assertListEqual(
            response.data['results'],
            self.serialize_course_run(expected, many=True, extra_context=extra_context)
        )

    def test_filter_by_keys(self):
        """ Verify the endpoint returns a list of course runs filtered by the specified keys. """
        CourseRun.objects.all().delete()
        expected = CourseRunFactory.create_batch(3, course__partner=self.partner)
        keys = ','.join([course.key for course in expected])
        url = '{root}?keys={keys}'.format(root=reverse('api:v1:course_run-list'), keys=keys)
        self.assert_list_results(url, expected)

    def test_filter_by_marketable(self):
        """ Verify the endpoint filters course runs to those that are marketable. """
        CourseRun.objects.all().delete()
        expected = CourseRunFactory.create_batch(3, course__partner=self.partner)
        for course_run in expected:
            SeatFactory(course_run=course_run)

        CourseRunFactory.create_batch(3, slug=None, course__partner=self.partner)
        CourseRunFactory.create_batch(3, slug='', course__partner=self.partner)

        url = reverse('api:v1:course_run-list') + '?marketable=1'
        self.assert_list_results(url, expected)

    def test_filter_by_hidden(self):
        """ Verify the endpoint filters course runs that are hidden. """
        CourseRun.objects.all().delete()
        course_runs = CourseRunFactory.create_batch(3, course__partner=self.partner)
        hidden_course_runs = CourseRunFactory.create_batch(3, hidden=True, course__partner=self.partner)
        url = reverse('api:v1:course_run-list')
        self.assert_list_results(url, course_runs + hidden_course_runs)
        url = reverse('api:v1:course_run-list') + '?hidden=False'
        self.assert_list_results(url, course_runs)

    def test_filter_by_active(self):
        """ Verify the endpoint filters course runs to those that are active. """
        CourseRun.objects.all().delete()

        # Create course with end date in future and enrollment_end in past.
        end = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=2)
        enrollment_end = datetime.datetime.now(pytz.UTC) - datetime.timedelta(days=1)
        CourseRunFactory(end=end, enrollment_end=enrollment_end, course__partner=self.partner)

        # Create course with end date in past and no enrollment_end.
        end = datetime.datetime.now(pytz.UTC) - datetime.timedelta(days=2)
        CourseRunFactory(end=end, enrollment_end=None, course__partner=self.partner)

        # Create course with end date in future and enrollment_end in future.
        end = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=2)
        enrollment_end = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=1)
        active_enrollment_end = CourseRunFactory(end=end, enrollment_end=enrollment_end, course__partner=self.partner)

        # Create course with end date in future and no enrollment_end.
        active_no_enrollment_end = CourseRunFactory(end=end, enrollment_end=None, course__partner=self.partner)

        expected = [active_enrollment_end, active_no_enrollment_end]
        url = reverse('api:v1:course_run-list') + '?active=1'
        self.assert_list_results(url, expected)

    def test_filter_by_license(self):
        CourseRun.objects.all().delete()
        course_runs_cc = CourseRunFactory.create_batch(3, course__partner=self.partner, license='cc-by-sa')
        CourseRunFactory.create_batch(3, course__partner=self.partner, license='')

        url = reverse('api:v1:course_run-list') + '?license=cc-by-sa'
        self.assert_list_results(url, course_runs_cc)

    def test_list_exclude_utm(self):
        """ Verify the endpoint returns marketing URLs without UTM parameters. """
        url = reverse('api:v1:course_run-list') + '?exclude_utm=1'
        self.assert_list_results(url, CourseRun.objects.all(), extra_context={'exclude_utm': 1})

    def test_contains_single_course_run(self):
        """ Verify that a single course_run is contained in a query """
        qs = urllib.parse.urlencode({
            'query': 'id:course*',
            'course_run_ids': self.course_run.key,
        })
        url = '{}?{}'.format(reverse('api:v1:course_run-contains'), qs)
        response = self.client.get(url)
        assert response.status_code == 200
        self.assertEqual(
            response.data,
            {
                'course_runs': {
                    self.course_run.key: True
                }
            }
        )

    def test_contains_multiple_course_runs(self):
        qs = urllib.parse.urlencode({
            'query': 'id:course*',
            'course_run_ids': '{},{},{}'.format(self.course_run.key, self.course_run_2.key, 'abc')
        })
        url = '{}?{}'.format(reverse('api:v1:course_run-contains'), qs)

        response = self.client.get(url)
        assert response.status_code == 200
        self.assertDictEqual(
            response.data,
            {
                'course_runs': {
                    self.course_run.key: True,
                    self.course_run_2.key: True,
                    'abc': False
                }
            }
        )

    @ddt.data(
        {'params': {'course_run_ids': 'a/b/c'}},
        {'params': {'query': 'id:course*'}},
        {'params': {}}
    )
    @ddt.unpack
    def test_contains_missing_parameter(self, params):
        qs = urllib.parse.urlencode(params)
        url = '{}?{}'.format(reverse('api:v1:course_run-contains'), qs)

        response = self.client.get(url)
        assert response.status_code == 400

    def test_options(self):
        url = reverse('api:v1:course_run-detail', kwargs={'key': self.course_run.key})
        response = self.client.options(url)
        self.assertEqual(response.status_code, 200)

        data = response.data['actions']['PUT']
        self.assertEqual(data['level_type']['choices'],
                         [{'display_name': self.course_run.level_type.name_t,
                           'value': self.course_run.level_type.name_t},
                          {'display_name': self.course_run_2.level_type.name_t,
                           'value': self.course_run_2.level_type.name_t},
                          {'display_name': self.draft_course_run.level_type.name_t,
                           'value': self.draft_course_run.level_type.name_t}])
        self.assertEqual(data['content_language']['choices'],
                         [{'display_name': x.name, 'value': x.code} for x in
                             LanguageTag.objects.all().order_by('name')])
        self.assertGreater(LanguageTag.objects.count(), 0)

    def test_editable_list_gives_drafts(self):
        # We delete self.course_run_2 and self.draft_course_run here so we can test that specifically
        # draft and extra are the only ones showing up.
        self.course_run_2.delete()
        self.draft_course_run.delete()

        draft = CourseRunFactory(
            course__partner=self.partner, uuid=self.course_run.uuid, key=self.course_run.key, draft=True
        )
        self.course_run.draft_version = draft
        self.course_run.save()
        extra = CourseRunFactory(course__partner=self.partner)

        response = self.client.get(reverse('api:v1:course_run-list') + '?editable=1')
        actual_sorted = sorted(response.data['results'], key=lambda course_run: course_run['key'])
        expected_sorted = sorted(self.serialize_course_run([draft, extra], many=True),
                                 key=lambda course_run: course_run['key'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(actual_sorted, expected_sorted)

    @responses.activate
    def test_editable_list_is_denied_as_normal_user(self):
        """ Verify that GET with editable=1 can't be reached by a normal unprivileged user. """
        self.user.is_staff = False
        self.user.save()

        response = self.client.get(reverse('api:v1:course_run-list') + '?editable=1')
        self.assertEqual(response.status_code, 403)

    def test_editable_get_gives_drafts(self):
        draft = CourseRunFactory(
            course__partner=self.partner, uuid=self.course_run.uuid, key=self.course_run.key, draft=True
        )
        self.course_run.draft_version = draft
        self.course_run.save()
        extra = CourseRunFactory(course__partner=self.partner)

        response = self.client.get(
            reverse('api:v1:course_run-detail', kwargs={'key': self.course_run.key}) + '?editable=1'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.serialize_course_run(draft, many=False))

        response = self.client.get(reverse('api:v1:course_run-detail', kwargs={'key': extra.key}) + '?editable=1')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.serialize_course_run(extra, many=False))

    def test_list_query_with_editable_raises_exception(self):
        """ Verify the endpoint raises an exception if both a q param and editable=1 are passed in """
        query = 'title:Some random title'
        url = '{root}?q={query}&editable=1'.format(root=reverse('api:v1:course_run-list'), query=query)

        with pytest.raises(EditableAndQUnsupported) as exc:
            self.client.get(url)

        self.assertEqual(str(exc.value), 'Specifying both editable=1 and a q parameter is not supported.')

    @ddt.data(
        ({
            'staff': True,
            'body': {
                'status': 'review_by_internal',
                'has_ofac_restrictions': True,
                'ofac_comment': 'United States'
            },
            'original_status': 'review_by_legal',
            'status_code': 200
        }),
        ({
            'staff': True,
            'body': {
                'status': 'review_by_internal',
                'has_ofac_restrictions': True,
                'ofac_comment': 'United States',
                'invalid_field': 'invalid value'
            },
            'original_status': 'review_by_legal',
            'status_code': 400
        }),
        ({
            'staff': True,
            'body': {
                'status': 'review_by_internal',
                'has_ofac_restrictions': True,
                'ofac_comment': 'United States'
            },
            'original_status': 'unpublished',
            'status_code': 400,
        }),
    )
    def test_change_status_and_ofac_info(self, patch_transaction):
        """Verify status, ofac restrictions, and ofac comment can be updated.  Test cases: valid body, invalid body"""
        self.user.is_staff = patch_transaction['staff']
        self.user.save()
        self.draft_course_run.status = patch_transaction['original_status']
        self.draft_course_run.save()
        group = Group.objects.get(name='Internal Users')
        self.user.groups.add(group)
        url = reverse('api:v1:course_run-detail', kwargs={'key': self.draft_course_run.key})
        response = self.client.patch(url, patch_transaction['body'], format='json')

        self.assertEqual(response.status_code, patch_transaction['status_code'])
