import logging

from django.core.management import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils.translation import ugettext as _

from course_discovery.apps.course_metadata.models import BackpopulateCourseTypeConfig, Course, CourseType

logger = logging.getLogger(__name__)


# This command is designed to help fill out the new-style 'type' fields for Courses and CourseRuns.
# These fields are a more explicit declaration for what sort of enrollment modes a course supports.
# Whereas before, you'd have to examine the seats and entitlements for a course/run to see what sort of
# course it was (i.e. is it credit? is it verified?).
#
# Which is what this command does - it tries to match the existing seat/entitlement profile for a course and
# its runs. Then set a matching CourseType and CourseRunType for each.
#
# This is idempotent.
# This does not change existing type fields.
# But it will validate existing type fields (catch any that don't match the seat/entitlement profile).
# This fills in any missing gaps (like a new rerun without a type in a course with a type).
# If there are multiple matching CourseTypes, this will prefer the one that was created earlier.
# If this can't find or assign a type for a course or any run inside that course, it will fail noisily but continue.
# This updates both draft and official rows (but does not require the same result for each).


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

    def is_matching_run_type(self, run, run_type):
        run_seat_types = set(run.seats.values_list('type', flat=True))
        type_seat_types = set(run_type.tracks.values_list('seat_type__slug', flat=True))
        return run_seat_types == type_seat_types

    def match_course_type(self, course, course_type, commit=False):
        matches = {}

        # First, easy exit if entitlements don't match.
        course_entitlement_modes = set(course.entitlements.values_list('mode', flat=True))
        type_entitlement_modes = set(course_type.entitlement_types.values_list('id', flat=True))
        # Allow old courses without entitlements by checking if it has any first
        mismatched_entitlements = course_entitlement_modes and course_entitlement_modes != type_entitlement_modes
        mismatched_existing_course_type = course.type and course.type != course_type
        if mismatched_entitlements or mismatched_existing_course_type:
            if mismatched_entitlements and course.type and course.type == course_type:
                logger.info(
                    _("Existing course type {type} for {key} ({id}) doesn't match its own entitlements.").format(
                        type=course.type.name, key=course.key, id=course.id,
                    )
                )
            return False
        if not course.type:
            matches[course] = course_type

        course_run_types = course_type.course_run_types.all()

        # Now, let's look at seat types too. If any of our CourseRunType children match a run, we'll take it.
        for run in course.course_runs.order_by('key'):  # ordered just for visible message reliability
            # Catch existing type data that doesn't match this attempted type
            if run.type and run.type not in course_run_types:
                logger.info(
                    _("Existing run type {run_type} for {key} ({id}) doesn't match course type {type}."
                      "Skipping type.").format(run_type=run.type.name, key=run.key, id=run.id, type=course_type.name)
                )
                return False

            run_types = [run.type] if run.type else course_run_types
            match = None
            for run_type in run_types:
                if self.is_matching_run_type(run, run_type):
                    match = run_type
                    break

            if not match:
                if run.type:
                    logger.info(_("Existing run type {run_type} for {key} ({id}) doesn't match its own seats.").format(
                        run_type=run.type.name, key=run.key, id=run.id,
                    ))
                return False

            if not run.type:
                matches[run] = match

        # OK, everything has a matching type! Course and all our runs! Yay!

        if not matches:
            # We already had *all* our type fields filled out, no need to do anything (if we actively didn't match,
            # we'd have already early exited False)
            return True

        logger.info(
            _('Course {key} ({id}) matched type {type}').format(key=course.key, id=course.id, type=course_type.name)
        )

        if commit:
            try:
                with transaction.atomic():
                    for obj, obj_type in matches.items():
                        obj.type = obj_type
                        obj.save()
            except Exception:  # pylint: disable=broad-except
                logger.exception(_('Could not convert course {key} ({id}) to type {type}').format(
                    key=course.key, id=course.id, type=course_type.name
                ))
                return False

        return True

    def backpopulate_course(self, course, course_types, commit):
        # Go through all types, and use the first one that matches. No sensible thing to do if multiple matched...
        for course_type in course_types:
            if self.match_course_type(course, course_type, commit):
                return True

        return False

    def backpopulate(self, options):
        # Manually check required partner field (doesn't use required=True, because that would require --partner
        # even when using --args-from-database)
        if options['partner'] is None:
            self.print_help('manage.py', 'backpopulate_course_type')
            raise CommandError(_('You must specify --partner'))

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
            if not self.backpopulate_course(course, course_types, options['commit']):
                failures.add(course)

        if failures:
            keys = sorted('{key} ({id})'.format(key=failure.key, id=failure.id) for failure in failures)
            raise CommandError(
                _('Could not backpopulate a course type for the following courses: {course_keys}').format(
                    course_keys=', '.join(keys)
                )
            )

    def handle(self, *args, **options):
        if options['args_from_database']:
            options = self.get_args_from_database()

        self.backpopulate(options)
