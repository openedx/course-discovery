"""
Unit tests for the `update_course_ai_languages` management command.
"""
import datetime
from unittest.mock import patch

import ddt
from django.core.management import CommandError, call_command
from django.test import TestCase
from django.utils.timezone import now

from course_discovery.apps.course_metadata.models import CourseRun, CourseRunType
from course_discovery.apps.course_metadata.tests.factories import CourseRunFactory, PartnerFactory, SeatFactory


@ddt.ddt
@patch('course_discovery.apps.core.api_client.lms.LMSAPIClient.get_course_run_translations_and_transcriptions')
class UpdateCourseAiLanguagesTests(TestCase):
    """Test Suite for the update_course_ai_languages management command."""

    AI_LANGUAGES_DATA = {
        'available_translation_languages': [
            {'code': 'fr', 'label': 'French'},
            {'code': 'cs', 'label': 'Czech'}
        ],
        'feature_enabled': True,
    }

    AI_LANGUAGES_DATA_WITH_TRANSCRIPTIONS = {
        **AI_LANGUAGES_DATA,
        'transcription_languages': ['da', 'fr']
    }

    def setUp(self):
        self.partner = PartnerFactory()
        self.course_run = CourseRunFactory()

    def assert_ai_langs(self, run, data):
        self.assertListEqual(
            run.ai_languages['translation_languages'],
            data['available_translation_languages']
        )
        self.assertListEqual(
            run.ai_languages['transcription_languages'],
            [{'code': lang_code, 'label': lang_code} for lang_code in data.get('transcription_languages', [])]
        )


    @ddt.data(AI_LANGUAGES_DATA, AI_LANGUAGES_DATA_WITH_TRANSCRIPTIONS)
    def test_update_ai_languages(self, mock_data, mock_get_translations_and_transcriptions):
        """Test the command with a valid course run and response data."""
        mock_get_translations_and_transcriptions.return_value = mock_data

        call_command('update_course_ai_languages', partner=self.partner.name)

        course_run = CourseRun.objects.get(id=self.course_run.id)
        self.assert_ai_langs(course_run, mock_data)

    @ddt.data(AI_LANGUAGES_DATA, AI_LANGUAGES_DATA_WITH_TRANSCRIPTIONS)
    def test_update_ai_languages_draft(self, mock_data, mock_get_translations_and_transcriptions):
        """
        Test the command with both draft and non-draft course runs, ensuring that the both draft and non-draft
        course runs are updated appropriately.
        """
        mock_get_translations_and_transcriptions.return_value = mock_data
        draft_course_run = CourseRunFactory(
            draft=True, end=now() + datetime.timedelta(days=10)
        )
        course_run = CourseRunFactory(draft=False, draft_version_id=draft_course_run.id)

        call_command('update_course_ai_languages', partner=self.partner.name)

        course_run.refresh_from_db()
        self.assert_ai_langs(course_run, mock_data)

        draft_course_run.refresh_from_db()
        self.assert_ai_langs(draft_course_run, mock_data)


    @ddt.data(AI_LANGUAGES_DATA, AI_LANGUAGES_DATA_WITH_TRANSCRIPTIONS)
    def test_update_ai_languages_no_translations(self, mock_data, mock_get_translations_and_transcriptions):
        """Test the command when no translations are returned for a course run."""
        mock_get_translations_and_transcriptions.return_value = {
            **mock_data,
            'available_translation_languages': [],
        }

        call_command('update_course_ai_languages', partner=self.partner.name)

        course_run = CourseRun.objects.get(id=self.course_run.id)
        self.assertListEqual(course_run.ai_languages['translation_languages'], [])

    @ddt.data(AI_LANGUAGES_DATA, AI_LANGUAGES_DATA_WITH_TRANSCRIPTIONS)
    def test_command_with_active_flag(self, mock_data, mock_get_translations_and_transcriptions):
        """Test the command with the active flag filtering active course runs."""
        mock_get_translations_and_transcriptions.return_value = mock_data

        active_course_run = CourseRunFactory(end=now() + datetime.timedelta(days=10), ai_languages=None)
        non_active_course_run = CourseRunFactory(end=now() - datetime.timedelta(days=10), ai_languages=None)

        call_command('update_course_ai_languages', partner=self.partner.name, active=True)

        active_course_run.refresh_from_db()
        non_active_course_run.refresh_from_db()

        self.assert_ai_langs(active_course_run, mock_data)
        assert non_active_course_run.ai_languages is None

    @ddt.data(AI_LANGUAGES_DATA, AI_LANGUAGES_DATA_WITH_TRANSCRIPTIONS)
    def test_command_with_marketable_flag(self, mock_data, mock_get_translations_and_transcriptions):
        """Test the command with the marketable flag filtering marketable course runs."""
        mock_get_translations_and_transcriptions.return_value = mock_data

        verified_and_audit_type = CourseRunType.objects.get(slug='verified-audit')
        verified_and_audit_type.is_marketable = True
        verified_and_audit_type.save()

        marketable_course_run = CourseRunFactory(
            status='published',
            slug='test-course-run',
            type=verified_and_audit_type,
            ai_languages=None
        )
        seat = SeatFactory(course_run=marketable_course_run)
        marketable_course_run.seats.add(seat)

        call_command('update_course_ai_languages', partner=self.partner.name, marketable=True)

        marketable_course_run.refresh_from_db()
        self.assert_ai_langs(marketable_course_run, mock_data)

    @ddt.data(AI_LANGUAGES_DATA, AI_LANGUAGES_DATA_WITH_TRANSCRIPTIONS)
    def test_command_with_marketable_and_active_flag(self, mock_data, mock_get_translations_and_transcriptions):
        """Test the command with the marketable and active flag filtering both marketable and active course runs."""
        mock_get_translations_and_transcriptions.return_value = mock_data

        non_active_non_marketable_course_run = CourseRunFactory(
            end=now() - datetime.timedelta(days=10), ai_languages=None
        )
        active_non_marketable_course_run = CourseRunFactory(
            end=now() + datetime.timedelta(days=10), ai_languages=None
        )

        verified_and_audit_type = CourseRunType.objects.get(slug='verified-audit')
        verified_and_audit_type.is_marketable = True
        verified_and_audit_type.save()

        marketable_non_active_course_run = CourseRunFactory(
            status='published',
            slug='test-course-run',
            type=verified_and_audit_type,
            end=now() - datetime.timedelta(days=10), ai_languages=None
        )
        seat = SeatFactory(course_run=marketable_non_active_course_run)
        marketable_non_active_course_run.seats.add(seat)

        call_command('update_course_ai_languages', partner=self.partner.name, marketable=True, active=True)

        marketable_non_active_course_run.refresh_from_db()
        active_non_marketable_course_run.refresh_from_db()
        non_active_non_marketable_course_run.refresh_from_db()
        self.assert_ai_langs(marketable_non_active_course_run, mock_data)
        self.assert_ai_langs(active_non_marketable_course_run, mock_data)
        assert non_active_non_marketable_course_run.ai_languages is None

    def test_command_no_partner(self, _):
        """Test the command raises an error if no valid partner is found."""
        with self.assertRaises(CommandError):
            call_command('update_course_ai_languages', partner='nonexistent-partner')
