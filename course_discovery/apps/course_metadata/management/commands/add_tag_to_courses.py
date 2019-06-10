from django.core.management import BaseCommand
from django.utils.translation import ugettext as _
from course_discovery.apps.course_metadata.models import Course
import argparse


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('tag', nargs=1, help=_("Tag to add to courses"))
        parser.add_argument('courses', nargs=argparse.REMAINDER, help=_('UUIDs of courses to tag'))

    def handle(self, *args, **options):
        self.add_tag_to_courses(options['tag'][0], options['courses'])

    def add_tag_to_courses(self, tag, courseUUIDs):
        courses = Course.objects.filter(uuid__in=courseUUIDs)
        for course in courses:
            course.topics.add(tag)
            course.save()
