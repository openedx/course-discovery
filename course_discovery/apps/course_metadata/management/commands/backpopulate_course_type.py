from django.core.management import BaseCommand, CommandError
from django.db.models import Q
from django.utils.translation import ugettext as _

from course_discovery.apps.course_metadata.data_loaders.course_type import calculate_course_type
from course_discovery.apps.course_metadata.models import BackpopulateCourseTypeConfig, Course, CourseRunType, CourseType


class Command(BaseCommand):
    help = _('Backpopulate new-style CourseType and CourseRunType where possible.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--partner',
            metavar=_('CODE'),
            help=_('Short code for a partner.'),
        )
        parser.add_argument(
            '--course',
            metavar=_('UUID'),
            action='append',
            help=_('Course to backpopulate.'),
            default=[],
        )
        parser.add_argument(
            '--org',
            metavar=_('KEY'),
            action='append',
            help=_('Organization to backpopulate.'),
            default=[],
        )
        parser.add_argument(
            '--allow-for',
            action='append',
            help=_('CourseType/CourseRunType mismatches to allow. Specify like course-type-slug:run-type-slug.'),
            default=[],
        )
        parser.add_argument(
            '--commit',
            action='store_true',
            help=_('Actually commit the changes to the database.'),
        )
        parser.add_argument(
            '--args-from-database',
            action='store_true',
            help=_('Use arguments from the BackpopulateCourseTypeConfig model instead of the command line.'),
        )

    def get_args_from_database(self):
        """ Returns an options dictionary from the current BackpopulateCourseTypeConfig model. """
        config = BackpopulateCourseTypeConfig.get_solo()

        # We don't need fancy shell-style whitespace/quote handling - none of our arguments are complicated
        argv = config.arguments.split()

        parser = self.create_parser('manage.py', 'backpopulate_course_type')
        return parser.parse_args(argv).__dict__   # we want a dictionary, not a non-iterable Namespace object

    def backpopulate(self, options):
        # Manually check required partner field (doesn't use required=True, because that would require --partner
        # even when using --args-from-database)
        if options['partner'] is None:
            self.print_help('manage.py', 'backpopulate_course_type')
            raise CommandError(_('You must specify --partner'))

        mismatches = {}
        if options['allow_for']:
            for value in options['allow_for']:
                course_type_slug, run_type_slug = value.split(':')
                if not CourseRunType.objects.filter(slug=run_type_slug).exists():
                    raise CommandError(_('Supplied Course Run Type slug [{rt_slug}] does not exist.').format(
                        rt_slug=run_type_slug
                    ))
                if course_type_slug in mismatches:
                    mismatches[course_type_slug].append(run_type_slug)
                else:
                    if not CourseType.objects.filter(slug=course_type_slug).exists():
                        raise CommandError(_('Supplied Course Type slug [{ct_slug}] does not exist.').format(
                            ct_slug=course_type_slug
                        ))
                    mismatches[course_type_slug] = [run_type_slug]

        # We look at both draft and official rows
        courses = Course.everything.filter(partner__short_code=options['partner']).filter(
            Q(uuid__in=options['course']) |
            Q(authoring_organizations__key__in=options['org'])
        ).distinct()
        if not courses:
            raise CommandError(_('No courses found. Did you specify an argument?'))

        failures = set()
        course_types = CourseType.objects.order_by('created')
        for course in courses:
            if not calculate_course_type(course, course_types=course_types, commit=options['commit'],
                                         mismatches=mismatches):
                failures.add(course)

        if failures:
            keys = sorted(f'{failure.key} ({failure.id})' for failure in failures)
            raise CommandError(
                _('Could not backpopulate a course type for the following courses: {course_keys}').format(
                    course_keys=', '.join(keys)
                )
            )

    def handle(self, *args, **options):
        if options['args_from_database']:
            options = self.get_args_from_database()

        self.backpopulate(options)
