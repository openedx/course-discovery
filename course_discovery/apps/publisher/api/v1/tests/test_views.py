import json

import mock
import responses
from django.urls import reverse
from rest_framework.test import APITestCase

from course_discovery.apps.core.models import Partner
from course_discovery.apps.core.tests.factories import StaffUserFactory, UserFactory
from course_discovery.apps.course_metadata.models import CourseRun, Video
from course_discovery.apps.course_metadata.tests.factories import OrganizationFactory, PersonFactory
from course_discovery.apps.ietf_language_tags.models import LanguageTag
from course_discovery.apps.publisher.api.v1.views import CourseRunViewSet
from course_discovery.apps.publisher.tests.factories import CourseRunFactory


class CourseRunViewSetTests(APITestCase):
    def test_without_authentication(self):
        self.client.logout()
        url = reverse('publisher:api:v1:course_run-publish', kwargs={'pk': 1})
        response = self.client.post(url, {})
        assert response.status_code == 401

    def test_without_authorization(self):
        user = UserFactory()
        self.client.force_login(user)
        url = reverse('publisher:api:v1:course_run-publish', kwargs={'pk': 1})
        response = self.client.post(url, {})
        assert response.status_code == 403

    def _create_course_run_for_publication(self):
        organization = OrganizationFactory()
        transcript_languages = [LanguageTag.objects.first()]
        return CourseRunFactory(
            course__organizations=[organization],
            course__tertiary_subject=None,
            lms_course_id='a/b/c',
            transcript_languages=transcript_languages,
            staff=PersonFactory.create_batch(2)
        )

    def _set_test_client_domain_and_login(self, partner):
        # pylint:disable=attribute-defined-outside-init
        self.client = self.client_class(SERVER_NAME=partner.site.domain)
        self.client.force_login(StaffUserFactory())

    def _mock_studio_api_success(self, publisher_course_run):
        partner = publisher_course_run.course.organizations.first().partner
        body = {'id': publisher_course_run.lms_course_id}
        url = '{root}/api/v1/course_runs/{key}/'.format(
            root=partner.studio_url.strip('/'),
            key=publisher_course_run.lms_course_id
        )
        responses.add(responses.PATCH, url, json=body, status=200)
        url = '{root}/api/v1/course_runs/{key}/images/'.format(
            root=partner.studio_url.strip('/'),
            key=publisher_course_run.lms_course_id
        )
        responses.add(responses.POST, url, json=body, status=200)

    def _mock_ecommerce_api(self, publisher_course_run, status=200, body=None):
        partner = publisher_course_run.course.organizations.first().partner
        body = body or {'id': publisher_course_run.lms_course_id}
        url = '{root}publication/'.format(root=partner.ecommerce_api_url)
        responses.add(responses.POST, url, json=body, status=status)

    @responses.activate
    @mock.patch.object(Partner, 'access_token', return_value='JWT fake')
    def test_publish(self, mock_access_token):  # pylint: disable=unused-argument
        publisher_course_run = self._create_course_run_for_publication()
        partner = publisher_course_run.course.organizations.first().partner
        self._set_test_client_domain_and_login(partner)

        self._mock_studio_api_success(publisher_course_run)
        self._mock_ecommerce_api(publisher_course_run)

        url = reverse('publisher:api:v1:course_run-publish', kwargs={'pk': publisher_course_run.pk})
        response = self.client.post(url, {})
        assert response.status_code == 200
        assert len(responses.calls) == 3
        expected = {
            'discovery': CourseRunViewSet.PUBLICATION_SUCCESS_STATUS,
            'ecommerce': CourseRunViewSet.PUBLICATION_SUCCESS_STATUS,
            'studio': CourseRunViewSet.PUBLICATION_SUCCESS_STATUS,
        }
        assert response.data == expected

        discovery_course_run = CourseRun.objects.get(key=publisher_course_run.lms_course_id)
        publisher_course = publisher_course_run.course
        discovery_course = discovery_course_run.course

        # pylint: disable=no-member
        assert discovery_course_run.title_override == publisher_course_run.title_override
        assert discovery_course_run.short_description_override is None
        assert discovery_course_run.full_description_override is None
        assert discovery_course_run.start == publisher_course_run.start
        assert discovery_course_run.end == publisher_course_run.end
        assert discovery_course_run.enrollment_start == publisher_course_run.enrollment_start
        assert discovery_course_run.enrollment_end == publisher_course_run.enrollment_end
        assert discovery_course_run.pacing_type == publisher_course_run.pacing_type
        assert discovery_course_run.min_effort == publisher_course_run.min_effort
        assert discovery_course_run.max_effort == publisher_course_run.max_effort
        assert discovery_course_run.language == publisher_course_run.language
        assert discovery_course_run.weeks_to_complete == publisher_course_run.length
        assert discovery_course_run.learner_testimonials == publisher_course.learner_testimonial
        expected = set(publisher_course_run.transcript_languages.all())
        assert set(discovery_course_run.transcript_languages.all()) == expected
        assert set(discovery_course_run.video_translation_languages.all()) == {publisher_course_run.video_language}
        assert set(discovery_course_run.staff.all()) == set(publisher_course_run.staff.all())

        assert discovery_course.canonical_course_run == discovery_course_run
        assert discovery_course.partner == partner
        assert discovery_course.title == publisher_course.title
        assert discovery_course.short_description == publisher_course.short_description
        assert discovery_course.full_description == publisher_course.full_description
        assert discovery_course.level_type == publisher_course.level_type
        assert discovery_course.video == Video.objects.get(src=publisher_course.video_link)
        assert discovery_course.image == publisher_course.image
        assert discovery_course.outcome == publisher_course.expected_learnings
        expected = list(publisher_course_run.course.organizations.all())
        assert list(discovery_course.authoring_organizations.all()) == expected
        expected = {publisher_course.primary_subject, publisher_course.secondary_subject}
        assert set(discovery_course.subjects.all()) == expected

    def test_publish_missing_course_run(self):
        self.client.force_login(StaffUserFactory())
        url = reverse('publisher:api:v1:course_run-publish', kwargs={'pk': 1})
        response = self.client.post(url, {})
        assert response.status_code == 404

    @responses.activate
    @mock.patch.object(Partner, 'access_token', return_value='JWT fake')
    def test_publish_with_studio_api_error(self, mock_access_token):  # pylint: disable=unused-argument
        publisher_course_run = self._create_course_run_for_publication()
        partner = publisher_course_run.course.organizations.first().partner
        self._set_test_client_domain_and_login(partner)

        expected_error = {'error': 'Oops!'}
        url = '{root}/api/v1/course_runs/{key}/'.format(
            root=partner.studio_url.strip('/'),
            key=publisher_course_run.lms_course_id
        )
        responses.add(responses.PATCH, url, json=expected_error, status=500)
        self._mock_ecommerce_api(publisher_course_run)

        url = reverse('publisher:api:v1:course_run-publish', kwargs={'pk': publisher_course_run.pk})
        response = self.client.post(url, {})
        assert response.status_code == 502
        assert len(responses.calls) == 2
        expected = {
            'discovery': CourseRunViewSet.PUBLICATION_SUCCESS_STATUS,
            'ecommerce': CourseRunViewSet.PUBLICATION_SUCCESS_STATUS,
            'studio': 'FAILED: ' + json.dumps(expected_error),
        }
        assert response.data == expected

    @responses.activate
    @mock.patch.object(Partner, 'access_token', return_value='JWT fake')
    def test_publish_with_ecommerce_api_error(self, mock_access_token):  # pylint: disable=unused-argument
        publisher_course_run = self._create_course_run_for_publication()
        partner = publisher_course_run.course.organizations.first().partner
        self._set_test_client_domain_and_login(partner)

        expected_error = {'error': 'Oops!'}
        self._mock_studio_api_success(publisher_course_run)
        self._mock_ecommerce_api(publisher_course_run, status=500, body=expected_error)

        url = reverse('publisher:api:v1:course_run-publish', kwargs={'pk': publisher_course_run.pk})
        response = self.client.post(url, {})
        assert response.status_code == 502
        assert len(responses.calls) == 3
        expected = {
            'discovery': CourseRunViewSet.PUBLICATION_SUCCESS_STATUS,
            'ecommerce': 'FAILED: ' + json.dumps(expected_error),
            'studio': CourseRunViewSet.PUBLICATION_SUCCESS_STATUS,
        }
        assert response.data == expected
