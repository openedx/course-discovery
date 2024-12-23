"""
Management command for archiving bootcamps by course UUIDs.
"""
from django.core.management import BaseCommand, CommandError
from django.utils.translation import gettext as _

from course_discovery.apps.course_metadata.models import Bootcamp, ArchiveBootcampsConfig


class Command(BaseCommand):
    """
    Management command to archive a list of bootcamps specified by course UUIDs.
    Example:
    ./manage.py archive_bootcamps bootcamp0uuid bootcamp1uuid ...
    """

    help = 'Archive a list of bootcamps specified by course UUIDs'

    def add_arguments(self, parser):
        parser.add_argument(
            'bootcamps', nargs="*", help=_('UUIDs of bootcamps to archive')
        )
        parser.add_argument(
            '--args-from-database', action='store_true',
            help=_('Use arguments from the ArchiveBootcampsConfig model instead of the command line.')
        )

    def handle(self, *args, **options):
        if options['args_from_database']:
            config = ArchiveBootcampsConfig.get_solo()
            bootcamp_uuids = config.bootcamp_uuids
            if not bootcamp_uuids:
                raise CommandError(_('No bootcamp UUIDs found in the database configuration.'))
            bootcamp_uuids = bootcamp_uuids.split(", ")
        else:
            if not options['bootcamps']:
                raise CommandError(_('Missing required arguments'))
            bootcamp_uuids = options['bootcamps']

        self.archive_bootcamps(bootcamp_uuids)

    def archive_bootcamps(self, bootcamp_uuids):


    def get_args_from_database(self):
        config = ArchiveBootcampsConfig.get_solo()
        return {"bootcamps": config.bootcamp_uuids}
