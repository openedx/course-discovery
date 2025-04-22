"""
Management command to fetch translation and transcription information from the LMS and update the CourseRun model.
"""

import logging

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from course_discovery.apps.core.api_client.lms import LMSAPIClient
from course_discovery.apps.course_metadata.models import CourseRun, LanguageTag, Partner

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Fetches Content AI Translations and Transcriptions metadata from the LMS and updates the CourseRun model.'

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

    def save_run_with_validation(self, run):
        """
        Verify that the ai_languages field matches the `AI_LANG_SCHEMA` schema before saving
        """
        run.clean_fields()
        run.save(update_fields=["ai_languages"])

    def handle(self, *args, **options):
        """
        Example usage: ./manage.py update_course_ai_languages --partner=edx --active --marketable
        """
        partner_identifier = options.get('partner')
        partner = Partner.objects.filter(name__iexact=partner_identifier).first()
        DEPRECATED_LANGUAGE_CODES = {
            "iw": "Hebrew",
        }

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

        # Reduce the memory usage
        course_runs = course_runs.iterator()

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
                available_translation_languages = [
                    {'code': lang['code'], 'label': lang['label']} for lang in available_translation_languages
                ]

                transcription_langs_with_labels = []
                for lang_code in available_transcription_languages:
                    # Standardizing language codes to match between edx-val and course-discovery:
                    # - edx-val uses "zh_HANS", "zh_HANT", while course-discovery uses "zh-Hans", "zh-Hant"
                    # - edx-val uses "en-GB", whereas course-discovery uses "en-gb"
                    standardized_code = lang_code.replace("_", "-")

                    if lang_code in DEPRECATED_LANGUAGE_CODES:
                        label = DEPRECATED_LANGUAGE_CODES[lang_code]
                    else:
                        language_tag = LanguageTag.objects.filter(code__iexact=standardized_code).first()
                        if language_tag:
                            label = language_tag.name
                        else:
                            logger.error(f"Error: Missing language label for {lang_code}")
                            continue

                    transcription_langs_with_labels.append({"code": lang_code, "label": label})

                available_transcription_languages = transcription_langs_with_labels

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
