"""
Deduplicate course metadata history rows that were unnecessarily created while running
refresh_course_metadata.

This largely inherits the internals from the clean_duplicate_history management command
provided by django-simple-history, with only one minor tweak (to ignore the `modified`
field while comparing potentially duplicate records).

Usage: identical to clean_duplicate_history:

  python manage.py deduplicate_course_metadata_history --dry course_metadata.Course
  python manage.py deduplicate_course_metadata_history course_metadata.Course
  python manage.py deduplicate_course_metadata_history course_metadata.CourseRun

https://django-simple-history.readthedocs.io/en/latest/utils.html#clean-duplicate-history
"""
from simple_history.management.commands import clean_duplicate_history


class Command(clean_duplicate_history.Command):
    help = (
        "Deduplicate course metadata history rows that were unnecessarily created "
        "while running refresh_course_metadata."
    )

    def _check_and_delete(self, entry1, entry2, dry_run=True):
        """
        We override upstream's _check_and_delete method with our own which ignores
        changes in the `modified` field.
        """
        delta = entry1.diff_against(entry2)
        if set(delta.changed_fields).issubset({"modified"}):  # This is the only line that differs from upstream.
            if not dry_run:
                entry1.delete()
            return 1
        return 0
