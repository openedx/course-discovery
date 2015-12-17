from django.db import models
from django.utils.translation import ugettext_lazy as _
from django_extensions.db.models import TimeStampedModel


class Catalog(TimeStampedModel):
    name = models.CharField(max_length=255, null=False, blank=False, help_text=_('Catalog name'))
    query = models.TextField(null=False, blank=False, help_text=_('Query to retrieve catalog contents'))

    def __str__(self):
        return 'Catalog #{id}: {name}'.format(id=self.id, name=self.name)  # pylint: disable=no-member

    def courses(self):
        """ Returns the list of courses contained within this catalog.

        Returns:
            List of courses contained in this catalog.
        """
        return []

    def contains(self, course_ids):  # pylint: disable=unused-argument
        """ Determines if the given courses are contained in this catalog.

        Arguments:
            course_ids (str[]): List of course IDs

        Returns:
            dict: Mapping of course IDs to booleans indicating if course is
                  contained in this catalog.
        """
        return {}
