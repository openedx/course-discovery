import uuid

import mock
import pytest
from django.apps import apps
from django.test import TestCase
from factory import DjangoModelFactory
from testfixtures import LogCapture
from waffle.testutils import override_switch

from course_discovery.apps.core.models import Currency
from course_discovery.apps.course_metadata.models import (
    Curriculum, CurriculumCourseMembership, DataLoaderConfig, DeletePersonDupsConfig, DrupalPublishUuidConfig,
    ProfileImageDownloadConfig, ProgramType, Seat, SubjectTranslation, TopicTranslation, TagCourseUuidsConfig
)
from course_discovery.apps.course_metadata.tests import factories

LOGGER_NAME = 'course_discovery.apps.course_metadata.signals'


@pytest.mark.django_db
@mock.patch('course_discovery.apps.api.cache.set_api_timestamp')
class TestCacheInvalidation:
    def test_model_change(self, mock_set_api_timestamp):
        """
        Verify that the API cache is invalidated after course_metadata models
        are saved or deleted.
        """
        factory_map = {}
        for factorylike in factories.__dict__.values():
            if isinstance(factorylike, type) and issubclass(factorylike, DjangoModelFactory):
                if getattr(factorylike, '_meta', None) and factorylike._meta.model:
                    factory_map[factorylike._meta.model] = factorylike

        # These are the models whose post_save and post_delete signals we're
        # connecting to. We want to test each of them.
        for model in apps.get_app_config('course_metadata').get_models():
            # Ignore models that aren't exposed by the API or are only used for testing.
            if model in [DataLoaderConfig, DeletePersonDupsConfig, DrupalPublishUuidConfig, SubjectTranslation,
                         TopicTranslation, ProfileImageDownloadConfig, TagCourseUuidsConfig]:
                continue
            if 'abstract' in model.__name__.lower() or 'historical' in model.__name__.lower():
                continue

            factory = factory_map.get(model)
            if not factory:
                pytest.fail('The {} model is missing a factory.'.format(model))

            # Verify that model creation and deletion invalidates the API cache.
            instance = factory()

            assert mock_set_api_timestamp.called
            mock_set_api_timestamp.reset_mock()

            instance.delete()

            assert mock_set_api_timestamp.called
            mock_set_api_timestamp.reset_mock()


class SeatSignalsTests(TestCase):
    """ Tests for the signal to save seats model into database """
    def setUp(self):
        self.course_runs = factories.CourseRunFactory.create_batch(3)
        self.partner = factories.PartnerFactory()
        self.course = self.course_runs[0].course
        self.course.partner = self.partner
        self.course_run = self.course_runs[0]
        self.program_type = ProgramType.objects.get(slug='masters')
        self.degree = factories.DegreeFactory(courses=[self.course], type=self.program_type, partner=self.partner)
        self.currency = Currency.objects.get(code='USD')
        self.curriculum = Curriculum.objects.create(program=self.degree, uuid=uuid.uuid4())
        self.curriculum_course = factories.CurriculumCourseMembershipFactory(
            curriculum=self.curriculum,
            course=self.course
        )

    @override_switch('masters_course_mode_enabled', active=False)
    @mock.patch('course_discovery.apps.core.models.OAuthAPIClient')
    def test_seat_post_save_waffle_inactive(self, mock_client_init):
        mock_client = mock_client_init.return_value

        Seat.objects.create(
            course_run=self.course_run,
            type=Seat.MASTERS,
            currency=self.currency
        )

        self.assertFalse(mock_client.get.called)

    @override_switch('masters_course_mode_enabled', active=True)
    @mock.patch('course_discovery.apps.core.models.OAuthAPIClient')
    def test_seat_post_save_waffle_flag_active(self, mock_client_init):
        mock_client = mock_client_init.return_value

        created_seat = Seat.objects.create(
            course_run=self.course_run,
            type=Seat.MASTERS,
            currency=self.currency
        )

        course_run_key = self.course_run.key
        expected_call_url = self.partner.lms_coursemode_api_url + 'courses/{}/'.format(course_run_key)
        expected_call_data = {
            'course_id': created_seat.course_run.key,
            'mode_slug': created_seat.type,
            'mode_display_name': created_seat.type.capitalize(),
            'currency': str(created_seat.currency.code) if created_seat.currency else '',
            'min_price': int(created_seat.price),
        }

        mock_client.post.assert_called_with(expected_call_url, json=expected_call_data)

    @override_switch('masters_course_mode_enabled', active=True)
    @mock.patch('course_discovery.apps.core.models.OAuthAPIClient')
    def test_seat_already_exists_waffle_flag_active(self, mock_client_init):
        mock_client = mock_client_init.return_value
        course_run_key = self.course_run.key
        mock_client.get.return_value.json.return_value = [
            {
                'course_id': course_run_key,
                'mode_slug': Seat.MASTERS
            }
        ]

        with LogCapture(LOGGER_NAME) as log:
            created_seat = Seat.objects.create(
                course_run=self.course_run,
                type=Seat.MASTERS,
                currency=self.currency
            )

            self.assertTrue(mock_client.get.called)
            self.assertFalse(mock_client.post.called)
            log.check(
                (
                    LOGGER_NAME,
                    'INFO',
                    'Creating [{}] track on LMS for [{}] while it already have the track.'.format(
                        created_seat.type,
                        course_run_key
                    )
                )
            )

    @override_switch('masters_course_mode_enabled', active=True)
    @mock.patch('course_discovery.apps.core.models.OAuthAPIClient')
    def test_seat_post_save_waffle_flag_active_bad_response(self, mock_client_init):
        mock_client = mock_client_init.return_value
        course_run_key = self.course_run.key
        mock_client.get.return_value.data = []
        mock_client.post.return_value.ok = False

        with LogCapture(LOGGER_NAME) as log:
            created_seat = Seat.objects.create(
                course_run=self.course_run,
                type=Seat.MASTERS,
                currency=self.currency
            )
            log.check(
                (
                    LOGGER_NAME,
                    'ERROR',
                    'Failed to add [{}] course_mode to course_run [{}] in course_mode api to LMS.'.format(
                        created_seat.type,
                        course_run_key
                    )
                )
            )

    @override_switch('masters_course_mode_enabled', active=True)
    @mock.patch('course_discovery.apps.core.models.OAuthAPIClient')
    def test_seat_post_save_empty_lms_url(self, mock_client_init):
        mock_client = mock_client_init.return_value
        self.partner.lms_url = ''
        self.partner.save()

        with LogCapture(LOGGER_NAME) as log:
            Seat.objects.create(
                course_run=self.course_run,
                type=Seat.MASTERS,
                currency=self.currency
            )

            self.assertFalse(mock_client.get.called)
            log.check(
                (
                    LOGGER_NAME,
                    'INFO',
                    'LMS api client is not initiated. Cannot publish [{}] track for [{}] course_run'.format(
                        Seat.MASTERS,
                        self.course_run.key
                    )
                )
            )

    @override_switch('masters_course_mode_enabled', active=True)
    @mock.patch('course_discovery.apps.core.models.OAuthAPIClient')
    def test_seat_post_save_empty_coursemode_api_url(self, mock_client_init):
        mock_client = mock_client_init.return_value
        self.partner.lms_coursemode_api_url = ''
        self.partner.save()

        with LogCapture(LOGGER_NAME) as log:
            Seat.objects.create(
                course_run=self.course_run,
                type=Seat.MASTERS,
                currency=self.currency
            )

            self.assertFalse(mock_client.get.called)
            log.check(
                (
                    LOGGER_NAME,
                    'INFO',
                    'No lms coursemode api url configured. Masters seat for course_run [{}] not published'.format(
                        self.course_run.key
                    ),
                )
            )


class CurriculumCourseMembershipTests(TestCase):
    """ Tests of the CurriculumCourseMembership model """
    def setUp(self):
        self.course_runs = factories.CourseRunFactory.create_batch(3)
        self.course = self.course_runs[0].course
        self.program_type = ProgramType.objects.get(slug='masters')
        self.partner = factories.PartnerFactory()
        self.degree = factories.DegreeFactory(courses=[self.course], type=self.program_type, partner=self.partner)
        self.curriculum = Curriculum.objects.create(program=self.degree, uuid=uuid.uuid4())

    @override_switch('masters_course_mode_enabled', active=False)
    def test_course_curriculum_membership_side_effect_flag_inactive(self):

        CurriculumCourseMembership.objects.create(
            course=self.course,
            curriculum=self.curriculum
        )

        for course_run in self.course_runs:
            for seat in course_run.seats.all():
                self.assertFalse(seat.type == Seat.MASTERS)

    @override_switch('masters_course_mode_enabled', active=True)
    def test_course_curriculum_membership_side_effect_flag_active(self):
        with mock.patch('course_discovery.apps.core.models.OAuthAPIClient'):
            CurriculumCourseMembership.objects.create(
                course=self.course,
                curriculum=self.curriculum
            )

            for course_run in self.course_runs:
                for seat in course_run.seats.all():
                    self.assertTrue(seat.type == Seat.MASTERS)

    @override_switch('masters_course_mode_enabled', active=True)
    def test_course_curriculum_membership_side_effect_not_masters(self):
        self.program_type.slug = 'not_masters'
        self.program_type.save()

        CurriculumCourseMembership.objects.create(
            course=self.course,
            curriculum=self.curriculum
        )

        for course_run in self.course_runs:
            for seat in course_run.seats.all():
                self.assertFalse(seat.type == Seat.MASTERS)
