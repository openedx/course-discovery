"""
Management command to fetch translation information from the LMS and update the CourseRun model.
"""

import logging

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from course_discovery.apps.core.api_client.lms import LMSAPIClient
from course_discovery.apps.course_metadata.models import CourseRun, Partner

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Fetches Content AI Translations metadata from the LMS and updates the CourseRun model in Discovery.'

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

    def handle(self, *args, **options):
        """
        Example usage: ./manage.py update_course_ai_translations --partner=edx --active --marketable
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
                translation_data = lms_api_client.get_course_run_translations(course_run.key)
                available_translation_languages = (
                    translation_data.get('available_translation_languages', [])
                    if translation_data.get('feature_enabled', False)
                    else []
                )
                available_transcription_languages = translation_data.get('transcription_languages', [])

                # Remove any keys other than `code` and `label`
                available_translation_languages = [{'code': lang['code'], 'label': lang['label']} for lang in available_translation_languages]

                # Add the labels for the codes. Currently we set the code as the label. We will be fixing this shortly
                available_transcription_languages = [{'code': lang, 'label': lang} for lang in available_transcription_languages]

                course_run.translation_languages = available_translation_languages
                course_run.save(update_fields=["translation_languages"])

                course_run.ai_languages = {
                    "translation_languages": available_translation_languages,
                    "transcription_languages": available_transcription_languages
                }
                course_run.save(update_fields=["ai_languages"])

                if course_run.draft_version:
                    course_run.draft_version.translation_languages = course_run.translation_languages
                    course_run.draft_version.save(update_fields=["translation_languages"])
                    logger.info(f'Updated translations for {course_run.key} (both draft and non-draft versions)')

                    course_run.draft_version.ai_languages = course_run.ai_languages
                    course_run.draft_version.save(update_fields=["ai_languages"])
                else:
                    logger.info(f'Updated translations for {course_run.key} (non-draft version only)')
            except Exception as e:  # pylint: disable=broad-except
                logger.error(f'Error processing {course_run.key}: {e}')
