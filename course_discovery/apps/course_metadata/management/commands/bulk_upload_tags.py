"""
Management command to add tags to courses
"""
import logging
import uuid

from django.core.management import BaseCommand, CommandError

from course_discovery.apps.course_metadata.models import BulkUploadTagsConfig, Course

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Add tags to courses from a csv file'

    def add_arguments(self, parser):
        parser.add_argument(
            '--csv_path',
            help='Path to the CSV file',
            type=str,
        )

    def handle(self, *args, **options):
        csv_path = options.get('csv_path', None)
        bulk_upload_tags_config = BulkUploadTagsConfig.current()

        try:
            if csv_path:
                file_handle = open(csv_path, "r")  # pylint: disable=consider-using-with
            else:
                file_handle = bulk_upload_tags_config.csv_file if bulk_upload_tags_config.is_enabled() else None
                file_handle.open('r')
        except Exception as exc:
            raise CommandError(  # pylint: disable=raise-missing-from
                "Error occured while opening the tags csv.\n{}".format(exc)
            )

        for line in file_handle:
            if line:
                course_uuid, tags = self.parse_line(line)
                self.set_course_tags(course_uuid, tags)

        file_handle.close()

    def parse_line(self, line):
        """
        uuid,tag1,tag2,tag3 -> uuid, [tag1, tag2, tag3]
        """
        ll = line.split(',')
        ll = list(map(lambda s: s.strip(), ll))
        return ll[0], ll[1:]

    def set_course_tags(self, course_uuid, tags):
        """Set the topics of course_uuid to match the ones in tags(list of strings)"""
        if self.is_valid_uuid(course_uuid):
            tags = list(filter(lambda s: s != '', tags))  # remove empty strings from tags
            logger.info(f'Adding tags for {course_uuid}')
            qs = Course.everything.filter(uuid=course_uuid)
            for course in qs:
                course.topics.set(tags)
                course.save()
        else:
            logger.info(f'{course_uuid} is not a valid uuid')

    def is_valid_uuid(self, val):
        """Check if val is a valid uuid"""
        try:
            uuid.UUID(str(val))
            return True
        except ValueError:
            return False
