"""
Management command to fetch translation and transcription information from the LMS and update the CourseRun model.
"""

import logging

from jsonschema import validate
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from course_discovery.apps.core.api_client.lms import LMSAPIClient
from course_discovery.apps.course_metadata.models import CourseRun, Partner
from course_discovery.apps.course_metadata.management.commands.constants import AI_LANG_SCHEMA

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Fetches Content AI Translations and Transcriptions metadata from the LMS and updates the CourseRun model in Discovery.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--partner',
            type=str,
            default=settings.DEFAULT_PARTNER_ID,
            help='Specify the partner name or ID to fetch translations for. '
                 'Defaults to the partner configured in settings.DEFAULT_PARTNER_ID.',
        )
        parser.add_argument(
            '--active',
            action='store_true',
            default=False,
            help='Only update translations for active course runs. Defaults to False.',
        )
        parser.add_argument(
            '--marketable',
            action='store_true',
            default=False,
            help='Only update translations for marketable course runs. Defaults to False.',
        )

    def save_run_with_validation(run):
        """
        Verify that the ai_languages field matches the `AI_LANG_SCHEMA` schema before saving
        """
        try:
            validate(run.ai_languages, AI_LANG_SCHEMA)
        except Exception as exc:
            raise ValidationError("Could not validate ai_languages field")

        run.save(update_fields=["ai_languages"])

    def handle(self, *args, **options):
        """
        Example usage: ./manage.py update_course_ai_languages --partner=edx --active --marketable
        """
        partner_identifier = options.get('partner')
        partner = Partner.objects.filter(name__iexact=partner_identifier).first()

        if not partner:
            raise CommandError('No partner object found. Ensure that the Partner data is correctly configured.')

        lms_api_client = LMSAPIClient(partner)

        course_runs = CourseRun.objects.all()

        if options['active'] and options['marketable']:
            course_runs = course_runs.marketable().union(course_runs.active())
        elif options['active']:
            course_runs = course_runs.active()
        elif options['marketable']:
            course_runs = course_runs.marketable()

        for course_run in course_runs:
            try:
                ai_languages_data = lms_api_client.get_course_run_translations_and_transcriptions(course_run.key)
                available_translation_languages = (
                    ai_languages_data.get('available_translation_languages', [])
                    if ai_languages_data.get('feature_enabled', False)
                    else []
                )
                available_transcription_languages = ai_languages_data.get('transcription_languages', [])

                # Remove any keys other than `code` and `label`
                available_translation_languages = [{'code': lang['code'], 'label': lang['label']} for lang in available_translation_languages]

                # Add the labels for the codes. Currently we set the code as the label. We will be fixing this in a follow-up PR
                available_transcription_languages = [{'code': lang, 'label': lang} for lang in available_transcription_languages]

                course_run.ai_languages = {
                    "translation_languages": available_translation_languages,
                    "transcription_languages": available_transcription_languages
                }
                self.save_run_with_validation(course_run)

                if course_run.draft_version:
                    course_run.draft_version.ai_languages = course_run.ai_languages
                    self.save_run_with_validation(course_run.draft_version)
                    logger.info(f'Updated ai languages for {course_run.key} (both draft and non-draft versions)')
                else:
                    logger.info(f'Updated ai languages for {course_run.key} (non-draft version only)')
            except Exception as e:  # pylint: disable=broad-except
                logger.error(f'Error processing {course_run.key}: {e}')
