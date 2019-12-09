import random

import responses
from django.urls import reverse

from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase, OAuth2Mixin
from course_discovery.apps.core.tests.factories import StaffUserFactory, UserFactory
from course_discovery.apps.core.tests.helpers import make_image_file
from course_discovery.apps.course_metadata.tests.factories import OrganizationFactory, PersonFactory
from course_discovery.apps.ietf_language_tags.models import LanguageTag
from course_discovery.apps.publisher.tests.factories import CourseRunFactory

PUBLISHER_UPGRADE_DEADLINE_DAYS = random.randint(1, 21)

LOGGER_NAME = 'course_discovery.apps.publisher.api.v1.views'


class CourseRunViewSetTests(OAuth2Mixin, APITestCase):

    def setUp(self):
        super().setUp()
        self.user = StaffUserFactory()
        self.client.force_login(self.user)

        # Two access tokens, because Studio pusher is using old rest API client and ecommerce pusher is using new one,
        # so their cache of the access token is not shared yet.
        self.mock_access_token()
        self.mock_access_token()

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
        organization = OrganizationFactory(partner=self.partner)
        transcript_languages = [LanguageTag.objects.first()]
        mock_image_file = make_image_file('test_image.jpg')
        return CourseRunFactory(
            course__organizations=[organization],
            course__tertiary_subject=None,
            course__image__from_file=mock_image_file,
            lms_course_id='a/b/c',
            transcript_languages=transcript_languages,
            staff=PersonFactory.create_batch(2),
            is_micromasters=1,
            micromasters_name="Micromasters",
        )

    def _mock_studio_api_success(self, publisher_course_run):
        body = {'id': publisher_course_run.lms_course_id}
        url = '{root}/api/v1/course_runs/{key}/'.format(
            root=self.partner.studio_url.strip('/'),
            key=publisher_course_run.lms_course_id
        )
        responses.add(responses.PATCH, url, json=body, status=200)
        url = '{root}/api/v1/course_runs/{key}/images/'.format(
            root=self.partner.studio_url.strip('/'),
            key=publisher_course_run.lms_course_id
        )
        responses.add(responses.POST, url, json=body, status=200)

    def _mock_ecommerce_api(self, publisher_course_run, status=200, body=None):
        body = body or {'id': publisher_course_run.lms_course_id}
        url = '{root}publication/'.format(root=self.partner.ecommerce_api_url)
        responses.add(responses.POST, url, json=body, status=status)

    def test_publish_missing_course_run(self):
        self.client.force_login(StaffUserFactory())
        url = reverse('publisher:api:v1:course_run-publish', kwargs={'pk': 1})
        response = self.client.post(url, {})
        assert response.status_code == 404
