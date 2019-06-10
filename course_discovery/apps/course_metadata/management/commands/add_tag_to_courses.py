from django.core.management import BaseCommand
from django.utils.translation import ugettext as _
from course_discovery.apps.course_metadata.models import Course


class Command(BaseCommand):
    """ Management command to add a single tag to a list of courses specified by uuid.
    Useful for tagging courses to be brought into prospectus, eg
    ./manage.py add_tag_to_courses myProspectusTag course0uuid course1uuid ... """

    help = 'Add single tag to a list of courses specified by uuid'

    def add_arguments(self, parser):
        parser.add_argument('tag', nargs=1, help=_("Tag to add to courses"))
        parser.add_argument('courses', nargs="+", help=_('UUIDs of courses to tag'))

    def handle(self, *args, **options):
        self.add_tag_to_courses(options['tag'][0], options['courses'])

    def add_tag_to_courses(self, tag, courseUUIDs):
        courses = Course.objects.filter(uuid__in=courseUUIDs)
        for course in courses:
            course.topics.add(tag)
            course.save()
