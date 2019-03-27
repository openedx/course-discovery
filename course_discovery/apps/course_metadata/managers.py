from django.db import models


class DraftManager(models.Manager):
    """ Model manager that hides draft rows unless you ask for them. """

    def get_queryset(self):
        return super().get_queryset().filter(draft=False)

    def with_drafts(self):
        return super().get_queryset()

    def find_drafts(self, **kwargs):
        """
        Acts like filter(), but prefers draft versions.
        If a draft is not available, we give back the non-draft version.

        This returns a list, not a queryset!
        """
        kwargs.pop('draft', None)  # Guard against accidental extra draft filtering here
        rows = self.with_drafts().filter(**kwargs)

        # We need to find matching rows (minus draft column), so grab the first unique together
        meta = self.model._meta  # pylint
        assert len(meta.unique_together) > 0, 'DraftManager requires unique_together for model ' + meta.object_name
        unique = list(meta.unique_together[0])
        unique.remove('draft')

        # Now group rows by that uniqueness constraint, preferring a draft result
        answers = {}
        for row in rows:
            key = tuple(getattr(row, field) for field in unique)
            if row.draft:
                answers[key] = row
            else:
                answers.setdefault(key, row)

        return list(answers.values())

    def filter_drafts(self, **kwargs):
        """
        Acts like filter(), but prefers draft versions.
        If a draft is not available, we give back the non-draft version.
        """
        drafts = self.find_drafts(**kwargs)
        ids = (x.id for x in drafts)
        return self.with_drafts().filter(id__in=ids)

    def get_draft(self, **kwargs):
        """
        Acts like get(), but prefers draft versions. (including raising exceptions like get does)
        If a draft is not available, we give back the non-draft version.
        """
        drafts = self.find_drafts(**kwargs)
        if not drafts:
            raise self.model.DoesNotExist()
        elif len(drafts) > 1:
            raise self.model.MultipleObjectsReturned()
        else:
            return drafts[0]
