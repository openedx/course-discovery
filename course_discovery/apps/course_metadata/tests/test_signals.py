import uuid
from datetime import datetime

import mock
import pytest
from django.apps import apps
from django.test import TestCase
from factory import DjangoModelFactory
from pytz import UTC
from waffle.testutils import override_switch

from course_discovery.apps.course_metadata.models import (
    Curriculum, CurriculumCourseMembership, DataLoaderConfig, DeletePersonDupsConfig, DrupalPublishUuidConfig,
    ProfileImageDownloadConfig, ProgramType, SubjectTranslation, TopicTranslation
)
from course_discovery.apps.course_metadata.signals import _seats_for_course_run
from course_discovery.apps.course_metadata.tests import factories


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
                         TopicTranslation, ProfileImageDownloadConfig]:
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
    @mock.patch('course_discovery.apps.course_metadata.signals.OAuthAPIClient')
    def test_course_curriculum_membership_side_effect_flag_inactive(self, mock_client_init):
        mock_client = mock_client_init.return_value

        CurriculumCourseMembership.objects.create(
            course=self.course,
            curriculum=self.curriculum
        )

        self.assertFalse(mock_client.put.called)

    @override_switch('masters_course_mode_enabled', active=True)
    @mock.patch('course_discovery.apps.course_metadata.signals.OAuthAPIClient')
    def test_course_curriculum_membership_side_effect_flag_active(self, mock_client_init):
        mock_client = mock_client_init.return_value

        CurriculumCourseMembership.objects.create(
            course=self.course,
            curriculum=self.curriculum
        )

        course_run_key = self.course_runs[0].key
        expected_call_url = self.partner.lms_commerce_api_url + 'courses/{}/'.format(course_run_key)
        expected_call_data = {
            'id': course_run_key,
            'modes': _seats_for_course_run(self.course_runs[0]),
        }

        mock_client.put.assert_called_with(expected_call_url, json=expected_call_data)

    @override_switch('masters_course_mode_enabled', active=True)
    @mock.patch('course_discovery.apps.course_metadata.signals.OAuthAPIClient')
    def test_course_curriculum_membership_side_effect_not_masters(self, mock_client_init):
        mock_client = mock_client_init.return_value
        self.program_type.slug = 'not_masters'
        self.program_type.save()

        CurriculumCourseMembership.objects.create(
            course=self.course,
            curriculum=self.curriculum
        )

        self.assertFalse(mock_client.put.called)

    @override_switch('masters_course_mode_enabled', active=True)
    @mock.patch('course_discovery.apps.course_metadata.signals.OAuthAPIClient')
    def test_course_curriculum_membership_side_effect_empty_commerce_api_url(self, mock_client_init):
        mock_client = mock_client_init.return_value
        self.partner.lms_commerce_api_url = ''
        self.partner.save()

        CurriculumCourseMembership.objects.create(
            course=self.course,
            curriculum=self.curriculum
        )

        self.assertFalse(mock_client.put.called)

    def test_seats_for_course_run_helper_method_has_seats(self):
        course_run = factories.CourseRunFactory(
            end=datetime(9999, 1, 1, tzinfo=UTC),
            enrollment_end=datetime(9999, 1, 1, tzinfo=UTC)
        )
        seat = factories.SeatFactory(course_run=course_run, upgrade_deadline=None)

        expected_seat_list = [{
            'bulk_sku': seat.bulk_sku,
            'currency': seat.currency.code,
            'expires': None,
            'name': seat.type,
            'price': int(seat.price),
            'sku': seat.sku
        }, {
            'bulk_sku': None,
            'currency': 'usd',
            'expires': None,
            'name': 'masters',
            'price': 0,
            'sku': None
        }]

        self.assertEqual(_seats_for_course_run(course_run), expected_seat_list)

    def test_seats_for_course_run_helper_method_no_seats(self):
        course_run = factories.CourseRunFactory(
            end=datetime(9999, 1, 1, tzinfo=UTC),
            enrollment_end=datetime(9999, 1, 1, tzinfo=UTC)
        )

        expected_seat_list = [{
            'bulk_sku': None,
            'currency': 'usd',
            'expires': None,
            'name': 'masters',
            'price': 0,
            'sku': None
        }]

        self.assertEqual(_seats_for_course_run(course_run), expected_seat_list)
