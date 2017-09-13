import mock
import responses
from django.urls import reverse
from rest_framework.test import APITestCase

from course_discovery.apps.core.models import Partner
from course_discovery.apps.core.tests.factories import StaffUserFactory, UserFactory
from course_discovery.apps.course_metadata.models import CourseRun, Video
from course_discovery.apps.course_metadata.tests.factories import OrganizationFactory
from course_discovery.apps.ietf_language_tags.models import LanguageTag
from course_discovery.apps.publisher.tests.factories import CourseRunFactory


class CourseRunViewSet(APITestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(StaffUserFactory())

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

    @responses.activate
    @mock.patch.object(Partner, 'access_token', return_value='JWT fake')
    def test_publish(self, mock_access_token):  # pylint: disable=unused-argument
        organization = OrganizationFactory()
        transcript_languages = [LanguageTag.objects.first()]
        publisher_course_run = CourseRunFactory(
            course__organizations=[organization],
            course__tertiary_subject=None,
            lms_course_id='a/b/c',
            transcript_languages=transcript_languages
        )
        partner = organization.partner

        # pylint:disable=attribute-defined-outside-init
        self.client = self.client_class(SERVER_NAME=partner.site.domain)
        self.client.force_login(StaffUserFactory())

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
        url = '{root}publication/'.format(root=partner.ecommerce_api_url)
        responses.add(responses.POST, url, json=body, status=200)

        url = reverse('publisher:api:v1:course_run-publish', kwargs={'pk': publisher_course_run.pk})
        response = self.client.post(url, {})
        assert response.status_code == 200
        assert len(responses.calls) == 3

        discovery_course_run = CourseRun.objects.get(key=publisher_course_run.lms_course_id)
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
        assert set(discovery_course_run.transcript_languages.all()) == set(transcript_languages)

        publisher_course = publisher_course_run.course
        discovery_course = discovery_course_run.course
        assert discovery_course.canonical_course_run == discovery_course_run
        assert discovery_course.partner == partner
        assert discovery_course.title == publisher_course.title
        assert discovery_course.short_description == publisher_course.short_description
        assert discovery_course.full_description == publisher_course.full_description
        assert discovery_course.level_type == publisher_course.level_type
        assert discovery_course.video == Video.objects.get(src=publisher_course.video_link)
        assert list(discovery_course.authoring_organizations.all()) == [organization]
        assert set(discovery_course.subjects.all()) == {publisher_course.primary_subject,
                                                        publisher_course.secondary_subject}

    def test_publish_missing_course_run(self):
        url = reverse('publisher:api:v1:course_run-publish', kwargs={'pk': 1})
        response = self.client.post(url, {})
        assert response.status_code == 404
