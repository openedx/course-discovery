import json

from django.db import models
from django.utils.translation import ugettext_lazy as _
from django_extensions.db.models import TimeStampedModel

from course_discovery.apps.course_metadata.models import Course


class Catalog(TimeStampedModel):
    name = models.CharField(max_length=255, null=False, blank=False, help_text=_('Catalog name'))
    query = models.TextField(null=False, blank=False, help_text=_('Query to retrieve catalog contents'))

    def __str__(self):
        return 'Catalog #{id}: {name}'.format(id=self.id, name=self.name)  # pylint: disable=no-member

    @property
    def query_as_dict(self):
        return json.loads(self.query)

    def courses(self):
        """ Returns the list of courses contained within this catalog.

        Returns:
            Course[]
        """

        return Course.search(self.query_as_dict)['results']

    def contains(self, course_ids):  # pylint: disable=unused-argument
        """ Determines if the given courses are contained in this catalog.

        Arguments:
            course_ids (str[]): List of course IDs

        Returns:
            dict: Mapping of course IDs to booleans indicating if course is
                  contained in this catalog.
        """
        query = self.query_as_dict['query']

        # Create a filtered query that includes that uses the catalog's query against a
        # collection of courses filtered using the passed in course IDs.
        filtered_query = {
            "query": {
                "filtered": {
                    "query": query,
                    "filter": {
                        "ids": {
                            "values": course_ids
                        }
                    }
                }
            }
        }

        contains = {course_id: False for course_id in course_ids}
        courses = Course.search(filtered_query)['results']
        for course in courses:
            contains[course.id] = True

        return contains
