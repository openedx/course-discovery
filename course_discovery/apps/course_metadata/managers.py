from django.db import models


class DraftManager(models.Manager):
    """ Model manager that hides draft rows unless you ask for them. """

    def get_queryset(self):
        return super().get_queryset().filter(draft=False)

    def with_drafts(self):
        return super().get_queryset()
