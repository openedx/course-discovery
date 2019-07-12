from django.core.management import BaseCommand, CommandError
from django.utils.translation import ugettext as _

from course_discovery.apps.course_metadata.models import Course, TagCourseUuidsConfig


class Command(BaseCommand):
    """ Management command to add a single tag to a list of courses specified by uuid.
    Useful for tagging courses to be brought into prospectus, eg
    ./manage.py add_tag_to_courses myProspectusTag course0uuid course1uuid ... """

    help = 'Add single tag to a list of courses specified by uuid'

    def add_arguments(self, parser):
        parser.add_argument('tag', nargs='?', help=_("Tag to add to courses"))
        parser.add_argument('courses', nargs="*", help=_('UUIDs of courses to tag'))
        parser.add_argument('--args-from-database', action='store_true',
                            help=_('Use arguments from the TagCourseUUIDsConfig model instead of the command line.')
                            )

    def handle(self, *args, **options):
        if options['args_from_database']:
            optionsDict = self.get_args_from_database()
            self.add_tag_to_courses(optionsDict['tag'], optionsDict['courses'].split())
        else:
            if options['tag'] is None or options['courses'] is None or options['courses'] == []:
                raise CommandError(_('Missing required arguments'))
            self.add_tag_to_courses(options['tag'], options['courses'])

    def add_tag_to_courses(self, tag, courseUUIDs):
        courses = Course.objects.filter(uuid__in=courseUUIDs)
        for course in courses:
            course.topics.add(tag)
            course.save()

    def get_args_from_database(self):
        config = TagCourseUuidsConfig.get_solo()
        return {"tag": config.tag, "courses": config.course_uuids}
