"""
Deduplicate course metadata history rows that were unnecessarily created while running
refresh_course_metadata.

This largely inherits the internals from the clean_duplicate_history management command
provided by django-simple-history, with only two minor tweaks:

1. Ignore the `modified` field while comparing potentially duplicate records.
2. Use the `everything` model manager while fetching all model instances to process.

Usage: identical to clean_duplicate_history:

  python manage.py deduplicate_course_metadata_history --dry course_metadata.Course
  python manage.py deduplicate_course_metadata_history course_metadata.Course
  python manage.py deduplicate_course_metadata_history course_metadata.CourseRun

https://django-simple-history.readthedocs.io/en/latest/utils.html#clean-duplicate-history
"""
from django.utils import timezone
from simple_history.management.commands import clean_duplicate_history


class Command(clean_duplicate_history.Command):
    help = (
        "Deduplicate course metadata history rows that were unnecessarily created "
        "while running refresh_course_metadata."
    )

    def _process(self, to_process, date_back=None, dry_run=True):
        """
        The body of this method is copied VERBATIM from upstream except for the
        following change:

        Instead of calling model.objects.all(), we use model.everything.all()
        whenever possible.
        """
        if date_back:
            stop_date = timezone.now() - timezone.timedelta(minutes=date_back)
        else:
            stop_date = None

        for model, history_model in to_process:
            m_qs = history_model.objects
            if stop_date:
                m_qs = m_qs.filter(history_date__gte=stop_date)
            found = m_qs.count()
            self.log(f"{model} has {found} historical entries", 2)
            if not found:
                continue

            # Break apart the query so we can add additional filtering

            # This try block is the only part that differs from upstream
            try:
                model_query = model.everything.all()  # Attempting to use the `everything` manager.
            except AttributeError:
                model_query = model.objects.all()  # upstream's original behavior.

            # If we're provided a stop date take the initial hit of getting the
            # filtered records to iterate over
            if stop_date:
                model_query = model_query.filter(
                    pk__in=(m_qs.values_list(model._meta.pk.name).distinct())
                )

            for o in model_query.iterator():
                self._process_instance(o, model, stop_date=stop_date, dry_run=dry_run)

    def _check_and_delete(self, entry1, entry2, dry_run=True):
        """
        The body of this method is copied VERBATIM from upstream except for the
        following change:

        Ignore changes in the `modified` field.
        """
        delta = entry1.diff_against(entry2)
        if set(delta.changed_fields).issubset({"modified"}):  # This is the only line that differs from upstream.
            if not dry_run:
                entry1.delete()
            return 1
        return 0
