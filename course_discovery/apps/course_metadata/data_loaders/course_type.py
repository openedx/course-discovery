import logging

from django.db import transaction
from django.utils.translation import ugettext as _

from course_discovery.apps.course_metadata.models import CourseRunType, CourseType

logger = logging.getLogger(__name__)


def _is_matching_run_type(run, run_type):
    run_seat_types = set(run.seats.values_list('type', flat=True))
    type_seat_types = set(run_type.tracks.values_list('seat_type__slug', flat=True))
    return run_seat_types == type_seat_types


def _do_entitlements_match(course, course_type):
    course_entitlement_modes = set(course.entitlements.values_list('mode', flat=True))
    type_entitlement_modes = set(course_type.entitlement_types.values_list('id', flat=True))

    # Allow old courses without entitlements by checking if it has any first
    mismatched_entitlements = course_entitlement_modes and course_entitlement_modes != type_entitlement_modes
    mismatched_existing_course_type = not course.type.empty and course.type != course_type
    if mismatched_entitlements or mismatched_existing_course_type:
        if mismatched_entitlements and not course.type.empty and course.type == course_type:
            logger.info(
                _("Existing course type {type} for {key} ({id}) doesn't match its own entitlements.").format(
                    type=course.type.name, key=course.key, id=course.id,
                )
            )
        return False

    return True


def _match_course_type(course, course_type, commit=False, mismatches=None):
    matches = {}

    # First, early exit if entitlements don't match.
    if not _do_entitlements_match(course, course_type):
        return False
    if course.type.empty:
        matches[course] = course_type

    course_run_types = course_type.course_run_types.order_by('created')

    if mismatches and course_type.slug in mismatches:
        # Using .order_by() here to reset the default ordering on these so we can eventually do the
        # order by created. This has to do with what operations are allowed on a union'ed QuerySet and that
        # our TimeStampedModels come with a default ordering.
        unmatched_course_run_types = CourseRunType.objects.filter(
            slug__in=mismatches[course_type.slug]
        ).order_by()
        course_run_types = course_run_types.order_by().union(unmatched_course_run_types).order_by('created')

    # Now, let's look at seat types too. If any of our CourseRunType children match a run, we'll take it.
    for run in course.course_runs.order_by('key'):  # ordered just for visible message reliability
        # Catch existing type data that doesn't match this attempted type
        if not run.type.empty and run.type not in course_run_types:
            logger.info(
                _("Existing run type {run_type} for {key} ({id}) doesn't match course type {type}."
                  "Skipping type.").format(run_type=run.type.name, key=run.key, id=run.id, type=course_type.name)
            )
            return False

        run_types = course_run_types if run.type.empty else [run.type]
        match = None
        for run_type in run_types:
            if _is_matching_run_type(run, run_type):
                match = run_type
                break

        if not match:
            if not run.type.empty:
                logger.info(_("Existing run type {run_type} for {key} ({id}) doesn't match its own seats.").format(
                    run_type=run.type.name, key=run.key, id=run.id,
                ))
            return False

        if run.type.empty:
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


# This has a fair bit of testing, but it's over in test_backpopulate_course_type.py
def calculate_course_type(course, course_types=None, commit=False, mismatches=None):
    """
    Calculate and set a CourseType or CourseRunType for the course and all runs in it, if possible.

    This method is designed to help fill out the new-style 'type' fields for Courses and CourseRuns.
    These fields are a more explicit declaration for what sort of enrollment modes a course supports.
    Whereas before, you'd have to examine the seats and entitlements for a course/run to see what sort of
    course it was (i.e. is it credit? is it verified?).

    Which is what this command does - it tries to match the existing seat/entitlement profile for a course and
    its runs. Then set a matching CourseType and CourseRunType for each.

    This is idempotent.
    This does not change existing type fields.
    But it will validate existing type fields (catch any that don't match the seat/entitlement profile).
    This fills in any missing gaps (like a new rerun without a type in a course with a type).
    If there are multiple matching CourseTypes, this will prefer the one that was created earlier.
    If this can't find or assign a type for a course or any run inside that course, it will log it and return False.
    This updates both draft and official rows (but does not require the same result for each).
    """
    if not course_types:
        course_types = CourseType.objects.order_by('created')

    # Go through all types, and use the first one that matches. No sensible thing to do if multiple matched...
    for course_type in course_types:
        if _match_course_type(course, course_type, commit=commit, mismatches=mismatches):
            return True

    return False
