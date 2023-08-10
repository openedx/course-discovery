import logging
import uuid

from django.core.management import BaseCommand

from course_discovery.apps.course_metadata.models import BulkModifyProgramHookConfig, Program

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """ Management command to bulk modify program hooks. Uses config BulkModifyProgramHooksConfig
    to be filled with the correct mapping of uuid to program text, entered as a new line separated list of
    <uuid>:<program_hook>
    ./manage.py modify_program_hooks """

    help = 'Modify program hooks in bulk with arguments from database'

    def handle(self, *args, **options):
        config = BulkModifyProgramHookConfig.get_solo()
        lines = config.program_hooks.split('\n')
        for line in lines:
            tokenized = line.split(':', 1)
            if len(tokenized) != 2:
                logger.warning(f'Incorrectly formatted line {line}')
                continue
            try:
                program_uuid = uuid.UUID(tokenized[0].strip())
                program = Program.objects.filter(uuid=program_uuid).first()
                if not program:
                    logger.warning('Cannot find program with uuid {uuid}'.format(uuid=tokenized[0]))
                    continue
                program.marketing_hook = tokenized[1]
                program.save(suppress_publication=True)
            except ValueError:
                logger.warning('Incorrectly formatted uuid "{uuid}"'.format(uuid=tokenized[0]))
                continue
