import datetime

import pytz
from django.db import models
from django.db.models.query_utils import Q

from course_discovery.apps.course_metadata.choices import ProgramStatus


class CourseQuerySet(models.QuerySet):
    def active(self):
        """ Filters Courses to those with CourseRuns that are either currently open for enrollment,
        or will be open for enrollment in the future. """

        now = datetime.datetime.now(pytz.UTC)
        return self.filter(
            (
                Q(course_runs__end__gt=now) | Q(course_runs__end__isnull=True)
            ) &
            (
                Q(course_runs__enrollment_end__gt=now) | Q(course_runs__enrollment_end__isnull=True)
            )
        )


class CourseRunQuerySet(models.QuerySet):
    def active(self):
        """ Returns CourseRuns that have not yet ended and meet the following enrollment criteria:
            - Open for enrollment
            - OR will be open for enrollment in the future
            - OR have no specified enrollment close date (e.g. self-paced courses)

        Returns:
            QuerySet
        """
        now = datetime.datetime.now(pytz.UTC)
        return self.filter(
            Q(end__gt=now) &
            (
                Q(enrollment_end__gt=now) |
                Q(enrollment_end__isnull=True)
            )
        )

    def marketable(self):
        """ Returns CourseRuns that can be marketed to learners.

         A CourseRun is considered marketable if it has a defined slug.

         Returns:
            QuerySet
         """

        return self.exclude(slug__isnull=True).exclude(slug='')


class ProgramQuerySet(models.QuerySet):
    def marketable(self):
        """ Returns Programs that can be marketed to learners.

         A Program is considered marketable if it is active and has a defined marketing slug.

         Returns:
            QuerySet
         """

        return self.filter(
            status=ProgramStatus.Active
        ).exclude(
            marketing_slug__isnull=True
        ).exclude(
            marketing_slug=''
        )
