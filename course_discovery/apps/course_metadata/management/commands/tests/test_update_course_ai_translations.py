"""
Unit tests for the `update_course_ai_translations` management command.
"""
import datetime
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import TestCase
from django.utils.timezone import now

from course_discovery.apps.course_metadata.models import CourseRun, CourseRunType
from course_discovery.apps.course_metadata.tests.factories import CourseRunFactory, PartnerFactory, SeatFactory


@patch('course_discovery.apps.core.api_client.lms.LMSAPIClient.get_course_run_translations')
class UpdateCourseAiTranslationsTests(TestCase):
    """Test Suite for the update_course_ai_translations management command."""

    TRANSLATION_DATA = {
        'available_translation_languages': [
            {'code': 'fr', 'label': 'French'},
            {'code': 'es', 'label': 'Spanish'}
        ],
        'feature_enabled': True
    }

    def setUp(self):
        self.partner = PartnerFactory()
        self.course_run = CourseRunFactory()

    def test_update_course_run_translations(self, mock_get_translations):
        """Test the command with a valid course run and translation data."""
        mock_get_translations.return_value = self.TRANSLATION_DATA

        call_command('update_course_ai_translations', partner=self.partner.name)

        course_run = CourseRun.objects.get(id=self.course_run.id)
        self.assertListEqual(
            course_run.translation_languages,
            self.TRANSLATION_DATA['available_translation_languages']
        )

    def test_command_with_no_translations(self, mock_get_translations):
        """Test the command when no translations are returned for a course run."""
        mock_get_translations.return_value = {
            **self.TRANSLATION_DATA,
            'available_translation_languages': [],
            'feature_enabled': False
        }

        call_command('update_course_ai_translations', partner=self.partner.name)

        course_run = CourseRun.objects.get(id=self.course_run.id)
        self.assertListEqual(course_run.translation_languages, [])

    def test_command_with_active_flag(self, mock_get_translations):
        """Test the command with the active flag filtering active course runs."""
        mock_get_translations.return_value = {
            **self.TRANSLATION_DATA,
            'available_translation_languages': [{'code': 'fr', 'label': 'French'}]
        }

        active_course_run = CourseRunFactory(end=now() + datetime.timedelta(days=10))
        non_active_course_run = CourseRunFactory(end=now() - datetime.timedelta(days=10), translation_languages=[])

        call_command('update_course_ai_translations', partner=self.partner.name, active=True)

        active_course_run.refresh_from_db()
        non_active_course_run.refresh_from_db()

        self.assertListEqual(
            active_course_run.translation_languages,
            [{'code': 'fr', 'label': 'French'}]
        )
        self.assertListEqual(non_active_course_run.translation_languages, [])

    def test_command_with_marketable_flag(self, mock_get_translations):
        """Test the command with the marketable flag filtering marketable course runs."""
        mock_get_translations.return_value = {
            **self.TRANSLATION_DATA,
            'available_translation_languages': [{'code': 'es', 'label': 'Spanish'}]
        }

        verified_and_audit_type = CourseRunType.objects.get(slug='verified-audit')
        verified_and_audit_type.is_marketable = True
        verified_and_audit_type.save()

        marketable_course_run = CourseRunFactory(
            status='published',
            slug='test-course-run',
            type=verified_and_audit_type
        )
        seat = SeatFactory(course_run=marketable_course_run)
        marketable_course_run.seats.add(seat)

        call_command('update_course_ai_translations', partner=self.partner.name, marketable=True)

        marketable_course_run.refresh_from_db()
        self.assertListEqual(
            marketable_course_run.translation_languages,
            [{'code': 'es', 'label': 'Spanish'}]
        )

    def test_command_no_partner(self, _):
        """Test the command raises an error if no valid partner is found."""
        with self.assertRaises(CommandError):
            call_command('update_course_ai_translations', partner='nonexistent-partner')
