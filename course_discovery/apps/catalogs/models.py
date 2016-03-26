from django.db import models
from django.utils.translation import ugettext_lazy as _
from django_extensions.db.models import TimeStampedModel
from haystack.query import SearchQuerySet

from course_discovery.apps.course_metadata.models import Course


class Catalog(TimeStampedModel):
    name = models.CharField(max_length=255, null=False, blank=False, help_text=_('Catalog name'))
    query = models.TextField(null=False, blank=False, help_text=_('Query to retrieve catalog contents'))

    def __str__(self):
        return 'Catalog #{id}: {name}'.format(id=self.id, name=self.name)  # pylint: disable=no-member

    def _get_query_results(self):
        """
        Returns the results of this Catalog's query.

        Returns:
            SearchQuerySet
        """
        return SearchQuerySet().models(Course).raw_search(self.query)

    def courses(self):
        """ Returns the list of courses contained within this catalog.

        Returns:
            Course[]
        """
        results = self._get_query_results().load_all()
        return [result.object for result in results]

    def contains(self, course_ids):  # pylint: disable=unused-argument
        """ Determines if the given courses are contained in this catalog.

        Arguments:
            course_ids (str[]): List of course IDs

        Returns:
            dict: Mapping of course IDs to booleans indicating if course is
                  contained in this catalog.
        """
        contains = {course_id: False for course_id in course_ids}
        results = self._get_query_results().filter(key__in=course_ids)
        for result in results:
            contains[result.get_stored_fields()['key']] = True

        return contains

    class Meta(TimeStampedModel.Meta):
        abstract = False
        permissions = (
            ('view_catalog', 'Can view catalog'),
        )
