import json
import random
from datetime import date

import mock
import pytest
import responses
from django.db.utils import IntegrityError
from django.test import override_settings
from django.urls import reverse
from testfixtures import LogCapture

from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase, OAuth2Mixin
from course_discovery.apps.core.models import Currency
from course_discovery.apps.core.tests.factories import StaffUserFactory, UserFactory
from course_discovery.apps.core.tests.helpers import make_image_file
from course_discovery.apps.core.utils import serialize_datetime
from course_discovery.apps.course_metadata.models import CourseEntitlement as DiscoveryCourseEntitlement
from course_discovery.apps.course_metadata.models import CourseRun, ProgramType
from course_discovery.apps.course_metadata.models import Seat as DiscoverySeat
from course_discovery.apps.course_metadata.models import Video
from course_discovery.apps.course_metadata.tests.factories import (
    CourseFactory, OrganizationFactory, PersonFactory, SeatTypeFactory
)
from course_discovery.apps.course_metadata.utils import (
    serialize_entitlement_for_ecommerce_api, serialize_seat_for_ecommerce_api
)
from course_discovery.apps.ietf_language_tags.models import LanguageTag
from course_discovery.apps.publisher.api.v1.views import CourseRunViewSet
from course_discovery.apps.publisher.models import CourseEntitlement, Seat
from course_discovery.apps.publisher.tests.factories import CourseEntitlementFactory, CourseRunFactory, SeatFactory

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

    @responses.activate
    def test_publish(self):  # pylint: disable=too-many-statements
        publisher_course_run = self._create_course_run_for_publication()
        currency = Currency.objects.get(code='USD')

        verified_entitlement = CourseEntitlementFactory(mode=CourseEntitlement.VERIFIED,
                                                        course=publisher_course_run.course,
                                                        currency=currency)

        common_seat_kwargs = {
            'course_run': publisher_course_run,
            'currency': currency,
        }
        audit_seat = SeatFactory(type=Seat.AUDIT, upgrade_deadline=None, **common_seat_kwargs)
        # The credit seat should NOT be published.
        SeatFactory(type=Seat.CREDIT, **common_seat_kwargs)
        professional_seat = SeatFactory(type=Seat.PROFESSIONAL, **common_seat_kwargs)
        verified_seat = SeatFactory(type=Seat.VERIFIED, **common_seat_kwargs)

        self._mock_studio_api_success(publisher_course_run)
        self._mock_ecommerce_api(publisher_course_run)
        with LogCapture(LOGGER_NAME) as log:
            url = reverse('publisher:api:v1:course_run-publish', kwargs={'pk': publisher_course_run.pk})
            response = self.client.post(url, {})
            assert response.status_code == 200
            log.check((LOGGER_NAME, 'INFO',
                       'Published course run with id: [{}] lms_course_id: [{}], user: [{}], date: [{}]'.format(
                           publisher_course_run.id, publisher_course_run.lms_course_id, self.user, date.today())))

        assert len(responses.calls) == 5
        expected = {
            'discovery': CourseRunViewSet.PUBLICATION_SUCCESS_STATUS,
            'ecommerce': CourseRunViewSet.PUBLICATION_SUCCESS_STATUS,
            'studio': CourseRunViewSet.PUBLICATION_SUCCESS_STATUS,
        }
        assert response.data == expected

        # Verify the correct deadlines were sent to the E-Commerce API
        ecommerce_body = json.loads(responses.calls[-1].request.body.decode('utf-8'))
        expected = [
            serialize_seat_for_ecommerce_api(audit_seat),
            serialize_seat_for_ecommerce_api(professional_seat),
            serialize_seat_for_ecommerce_api(verified_seat),
            serialize_entitlement_for_ecommerce_api(verified_entitlement),
        ]
        assert ecommerce_body['products'] == expected
        assert ecommerce_body['verification_deadline'] == serialize_datetime(publisher_course_run.end_date_temporary)

        discovery_course_run = CourseRun.objects.get(key=publisher_course_run.lms_course_id)
        publisher_course = publisher_course_run.course
        discovery_course = discovery_course_run.course

        assert ecommerce_body['id'] == publisher_course_run.lms_course_id
        assert ecommerce_body['uuid'] == str(discovery_course.uuid)

        # pylint: disable=no-member
        assert discovery_course_run.title_override == publisher_course_run.title_override
        assert discovery_course_run.short_description_override is None
        assert discovery_course_run.full_description_override is None
        assert discovery_course_run.start == publisher_course_run.start_date_temporary
        assert discovery_course_run.end == publisher_course_run.end_date_temporary
        assert discovery_course_run.pacing_type == publisher_course_run.pacing_type_temporary
        assert discovery_course_run.min_effort == publisher_course_run.min_effort
        assert discovery_course_run.max_effort == publisher_course_run.max_effort
        assert discovery_course_run.language == publisher_course_run.language
        assert discovery_course_run.weeks_to_complete == publisher_course_run.length
        assert discovery_course_run.has_ofac_restrictions == publisher_course_run.has_ofac_restrictions
        assert discovery_course_run.external_key == publisher_course_run.external_key
        expected = set(publisher_course_run.transcript_languages.all())
        assert set(discovery_course_run.transcript_languages.all()) == expected
        assert discovery_course_run.expected_program_type == ProgramType.objects.get(slug=ProgramType.MICROMASTERS)
        assert discovery_course_run.expected_program_name == 'Micromasters'
        assert set(discovery_course_run.staff.all()) == set(publisher_course_run.staff.all())

        assert discovery_course.canonical_course_run == discovery_course_run
        assert discovery_course.partner == self.partner
        assert discovery_course.title == publisher_course.title
        assert discovery_course.short_description == publisher_course.short_description
        assert discovery_course.full_description == publisher_course.full_description
        assert discovery_course.level_type == publisher_course.level_type
        assert discovery_course.video == Video.objects.get(src=publisher_course.video_link)
        assert discovery_course.image.name is not None
        assert discovery_course.image.url is not None
        assert discovery_course.image.file is not None
        assert discovery_course.image.small.url is not None
        assert discovery_course.image.small.file is not None
        assert discovery_course.outcome == publisher_course.expected_learnings
        assert discovery_course.prerequisites_raw == publisher_course.prerequisites
        assert discovery_course.syllabus_raw == publisher_course.syllabus
        assert discovery_course.learner_testimonials == publisher_course.learner_testimonial
        assert discovery_course.faq == publisher_course.faq
        assert discovery_course.additional_information == publisher_course.additional_information
        assert discovery_course.active_url_slug == publisher_course.url_slug
        expected = list(publisher_course_run.course.organizations.all())
        assert list(discovery_course.authoring_organizations.all()) == expected
        expected = {publisher_course.primary_subject, publisher_course.secondary_subject}
        assert set(discovery_course.subjects.all()) == expected

        self.assertEqual(1, DiscoveryCourseEntitlement.objects.all().count())
        DiscoveryCourseEntitlement.objects.get(
            mode=SeatTypeFactory.verified(),
            price=verified_entitlement.price,
            course=discovery_course,
            currency=currency,
        )

        common_seat_kwargs = {
            'course_run': discovery_course_run,
            'currency': currency,
        }
        DiscoverySeat.objects.get(type__slug=DiscoverySeat.AUDIT, _upgrade_deadline__isnull=True, **common_seat_kwargs)
        DiscoverySeat.objects.get(
            type__slug=DiscoverySeat.PROFESSIONAL,
            _upgrade_deadline__isnull=True,
            price=professional_seat.price,
            **common_seat_kwargs
        )
        DiscoverySeat.objects.get(
            type__slug=DiscoverySeat.VERIFIED,
            _upgrade_deadline=verified_seat.upgrade_deadline,
            price=verified_seat.price,
            **common_seat_kwargs
        )

    @responses.activate
    def test_publish_with_duplicate_url_slug(self):
        publisher_course_run = self._create_course_run_for_publication()
        publisher_course_run.course.url_slug = 'duplicate'
        publisher_course_run.course.save()
        discovery_matching_course = CourseFactory(draft=False, partner=publisher_course_run.course.partner)
        discovery_matching_course.set_active_url_slug('duplicate')
        discovery_matching_course.save()
        self._mock_studio_api_success(publisher_course_run)
        self._mock_ecommerce_api(publisher_course_run)

        with pytest.raises(IntegrityError):
            url = reverse('publisher:api:v1:course_run-publish', kwargs={'pk': publisher_course_run.pk})
            self.client.post(url, {})

        discovery_matching_course.draft = True
        discovery_matching_course.save()

        with pytest.raises(IntegrityError):
            url = reverse('publisher:api:v1:course_run-publish', kwargs={'pk': publisher_course_run.pk})
            self.client.post(url, {})

    def test_publish_to_existing_updates_slug_history(self):
        publisher_course_run = self._create_course_run_for_publication()
        publisher_course_run.course.url_slug = 'first'
        publisher_course_run.course.save()

        self._mock_studio_api_success(publisher_course_run)
        self._mock_ecommerce_api(publisher_course_run)

        publish_url = reverse('publisher:api:v1:course_run-publish', kwargs={'pk': publisher_course_run.pk})
        response = self.client.post(publish_url, {})
        assert response.status_code == 200

        publisher_course_run.course.url_slug = 'second'
        publisher_course_run.course.save()
        response = self.client.post(publish_url, {})
        assert response.status_code == 200

        discovery_course_run = CourseRun.objects.get(key=publisher_course_run.lms_course_id)
        discovery_course = discovery_course_run.course

        assert discovery_course.url_slug_history.count() == 2
        assert discovery_course.active_url_slug == 'second'
        assert discovery_course.url_slug_history.filter(url_slug='first', is_active=False).count() == 1

    @responses.activate
    @override_settings(PUBLISHER_UPGRADE_DEADLINE_DAYS=PUBLISHER_UPGRADE_DEADLINE_DAYS)
    def test_publish_seat_without_upgrade_deadline(self):
        publisher_course_run = self._create_course_run_for_publication()
        verified_seat = SeatFactory(type=Seat.VERIFIED, course_run=publisher_course_run, upgrade_deadline=None)

        self._mock_studio_api_success(publisher_course_run)
        self._mock_ecommerce_api(publisher_course_run)

        url = reverse('publisher:api:v1:course_run-publish', kwargs={'pk': publisher_course_run.pk})
        response = self.client.post(url, {})
        assert response.status_code == 200

        discovery_course_run = CourseRun.objects.get(key=publisher_course_run.lms_course_id)
        DiscoverySeat.objects.get(
            type__slug=DiscoverySeat.VERIFIED,
            _upgrade_deadline=verified_seat.calculated_upgrade_deadline,
            price=verified_seat.price,
            course_run=discovery_course_run
        )

    @responses.activate
    def test_publish_with_additional_organization(self):
        """
        Test that the publish button does not remove existing organization
        """
        publisher_course_run = self._create_course_run_for_publication()

        self._mock_studio_api_success(publisher_course_run)
        self._mock_ecommerce_api(publisher_course_run)

        publish_url = reverse('publisher:api:v1:course_run-publish', kwargs={'pk': publisher_course_run.pk})
        response = self.client.post(publish_url, {})
        assert response.status_code == 200
        discovery_course_run = CourseRun.objects.get(key=publisher_course_run.lms_course_id)
        publisher_course = publisher_course_run.course
        discovery_course = discovery_course_run.course
        assert discovery_course.authoring_organizations.all().count() == 1

        publisher_course.organizations.add(OrganizationFactory())
        response = self.client.post(publish_url, {})
        assert response.status_code == 200
        assert discovery_course.authoring_organizations.all().count() == 2

    @responses.activate
    def test_publish_with_staff_removed(self):
        """
        Test that the publish button adds and removes staff from discovery_course_run
        """
        publisher_course_run = self._create_course_run_for_publication()

        self._mock_studio_api_success(publisher_course_run)
        self._mock_ecommerce_api(publisher_course_run)

        publish_url = reverse('publisher:api:v1:course_run-publish', kwargs={'pk': publisher_course_run.pk})
        response = self.client.post(publish_url, {})
        assert response.status_code == 200
        discovery_course_run = CourseRun.objects.get(key=publisher_course_run.lms_course_id)
        assert discovery_course_run.staff.all().count() == 2

        publisher_course_run.staff.set(PersonFactory.create_batch(1))  # pylint: disable=no-member
        response = self.client.post(publish_url, {})
        assert response.status_code == 200
        discovery_course_run = CourseRun.objects.get(key=publisher_course_run.lms_course_id)
        assert discovery_course_run.staff.all().count() == 1

    def test_publish_missing_course_run(self):
        self.client.force_login(StaffUserFactory())
        url = reverse('publisher:api:v1:course_run-publish', kwargs={'pk': 1})
        response = self.client.post(url, {})
        assert response.status_code == 404

    @responses.activate
    def test_publish_with_studio_api_error(self):
        publisher_course_run = self._create_course_run_for_publication()
        SeatFactory(type=Seat.VERIFIED, course_run=publisher_course_run)

        expected_error = {'error': 'Oops!'}
        url = '{root}/api/v1/course_runs/{key}/'.format(
            root=self.partner.studio_url.strip('/'),
            key=publisher_course_run.lms_course_id
        )
        responses.add(responses.PATCH, url, json=expected_error, status=500)
        self._mock_ecommerce_api(publisher_course_run)

        url = reverse('publisher:api:v1:course_run-publish', kwargs={'pk': publisher_course_run.pk})
        response = self.client.post(url, {})
        assert response.status_code == 502
        assert len(responses.calls) == 4
        expected = {
            'discovery': CourseRunViewSet.PUBLICATION_SUCCESS_STATUS,
            'ecommerce': CourseRunViewSet.PUBLICATION_SUCCESS_STATUS,
            'studio': 'FAILED: ' + json.dumps(expected_error),
        }
        assert response.data == expected

    @responses.activate
    def test_publish_with_studio_image_error(self):
        publisher_course_run = self._create_course_run_for_publication()
        SeatFactory(type=Seat.VERIFIED, course_run=publisher_course_run)

        expected_error = {'error': 'Oops!'}
        url = '{root}/api/v1/course_runs/{key}/'.format(
            root=self.partner.studio_url.strip('/'),
            key=publisher_course_run.lms_course_id
        )
        responses.add(responses.PATCH, url, status=200)
        responses.add(responses.POST, url + '/images/', json=expected_error, status=400)
        self._mock_ecommerce_api(publisher_course_run)

        url = reverse('publisher:api:v1:course_run-publish', kwargs={'pk': publisher_course_run.pk})
        with mock.patch('course_discovery.apps.api.utils.logger.exception') as mock_logger:
            response = self.client.post(url, {})

        assert mock_logger.call_count == 1
        assert mock_logger.call_args_list[0] == mock.call(
            'An error occurred while setting the course run image for [{key}] in studio. All other fields '
            'were successfully saved in Studio.'.format(key=publisher_course_run.lms_course_id)
        )

        assert response.status_code == 200
        assert len(responses.calls) == 5
        expected = {
            'discovery': CourseRunViewSet.PUBLICATION_SUCCESS_STATUS,
            'ecommerce': CourseRunViewSet.PUBLICATION_SUCCESS_STATUS,
            'studio': CourseRunViewSet.PUBLICATION_SUCCESS_STATUS,
        }
        assert response.data == expected

    @responses.activate
    def test_publish_with_ecommerce_api_error(self):
        publisher_course_run = self._create_course_run_for_publication()
        SeatFactory(type=Seat.VERIFIED, course_run=publisher_course_run)

        expected_error = {'error': 'Oops!'}
        self._mock_studio_api_success(publisher_course_run)
        self._mock_ecommerce_api(publisher_course_run, status=500, body=expected_error)

        url = reverse('publisher:api:v1:course_run-publish', kwargs={'pk': publisher_course_run.pk})
        response = self.client.post(url, {})
        assert response.status_code == 502
        assert len(responses.calls) == 5
        expected = {
            'discovery': CourseRunViewSet.PUBLICATION_SUCCESS_STATUS,
            'ecommerce': 'FAILED: ' + str(expected_error),
            'studio': CourseRunViewSet.PUBLICATION_SUCCESS_STATUS,
        }
        assert response.data == expected

    @responses.activate
    def test_publish_masters_track_seat(self):
        """
        Test that publishing a seat with masters_track creates a masters seat and masters track
        """
        SeatTypeFactory.masters()  # ensure masters exists
        publisher_course_run = self._create_course_run_for_publication()
        audit_seat_with_masters_track = SeatFactory(type='audit', course_run=publisher_course_run, masters_track=True)
        publisher_course_run.seats.add(audit_seat_with_masters_track)

        self._mock_studio_api_success(publisher_course_run)
        self._mock_ecommerce_api(publisher_course_run)

        publish_url = reverse('publisher:api:v1:course_run-publish', kwargs={'pk': publisher_course_run.pk})
        response = self.client.post(publish_url, {})
        assert response.status_code == 200
        discovery_course_run = CourseRun.objects.get(key=publisher_course_run.lms_course_id)
        assert discovery_course_run.seats.all().count() == 2
        assert discovery_course_run.seats.filter(type__slug=DiscoverySeat.MASTERS).count() == 1
