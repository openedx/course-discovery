"""
Management command for updating course verticals and subverticals

Example usage:
    $ ./manage.py update_course_verticals

"""
import logging

import unicodecsv
from django.conf import settings
from django.core.management import BaseCommand, CommandError

from course_discovery.apps.course_metadata.models import Course
from course_discovery.apps.tagging.emails import send_email_for_course_verticals_update
from course_discovery.apps.tagging.models import CourseVertical, SubVertical, UpdateCourseVerticalsConfig, Vertical

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Update course verticals and subverticals"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.report = {
            'failures': [],
            'successes': [],
        }

    def handle(self, *args, **options):
        reader = self.get_csv_reader()

        for row in reader:
            try:
                course_key = row.get('course')
                self.process_vertical_information(row)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                self.report['failures'].append(
                    {
                        'id': course_key,  # pylint: disable=used-before-assignment
                        'reason': repr(exc)
                    }
                )
                logger.exception(f"Failed to set vertical/subvertical information for course with key {course_key}")
            else:
                self.report['successes'].append(
                    {
                        'id': course_key,
                    }
                )
                logger.info(f"Successfully set vertical and subvertical info for course with key {course_key}")

        send_email_for_course_verticals_update(self.report, settings.COURSE_VERTICALS_UPDATE_RECIPIENTS)

    def process_vertical_information(self, row):
        course_key, vertical_name, subvertical_name = row['course'], row['vertical'], row['subvertical']
        course = Course.objects.get(key=course_key)
        vertical = Vertical.objects.filter(name=vertical_name).first()
        subvertical = SubVertical.objects.filter(name=subvertical_name).first()
        if (not vertical and vertical_name) or (not subvertical and subvertical_name):
            raise ValueError("Incorrect vertical or subvertical provided")

        if (vertical and not vertical.is_active) or (subvertical and not subvertical.is_active):
            raise ValueError("The provided vertical or subvertical is not active")

        course_vertical = CourseVertical.objects.filter(course=course).first()
        if course_vertical:
            logger.info(f"Existing vertical association found for course with key {course_key}")
            course_vertical.vertical = vertical
            course_vertical.sub_vertical = subvertical
            course_vertical.save()
        else:
            CourseVertical.objects.create(course=course, vertical=vertical, sub_vertical=subvertical)

    def get_csv_reader(self):
        config = UpdateCourseVerticalsConfig.current()
        if not config.enabled:
            raise CommandError('Configuration object is not enabled')

        if not config.csv_file:
            raise CommandError('Configuration object does not have any input csv')

        reader = unicodecsv.DictReader(config.csv_file)
        return reader
