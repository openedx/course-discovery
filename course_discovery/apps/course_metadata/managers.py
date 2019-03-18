from django.db import models
from django.db.models import Q


class DraftManager(models.Manager):
    """ Model manager that hides draft rows unless you ask for them. """

    def get_queryset(self):
        return super().get_queryset().filter(draft=False)

    def _with_drafts(self):
        return super().get_queryset()

    def filter_drafts(self, **kwargs):
        """
        Acts like filter(), but prefers draft versions.
        If a draft is not available, we give back the non-draft version.
        """
        return self._with_drafts().filter(Q(draft=True) | Q(draft_version=None)).filter(**kwargs)

    def get_draft(self, **kwargs):
        """
        Acts like get(), but prefers draft versions. (including raising exceptions like get does)
        If a draft is not available, we give back the non-draft version.
        """
        return self.filter_drafts(**kwargs).get()
