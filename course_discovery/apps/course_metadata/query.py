import datetime

import pytz
from django.db import models
from django.db.models.query_utils import Q

from course_discovery.apps.course_metadata.choices import CourseRunStatus, ProgramStatus


class CourseQuerySet(models.QuerySet):
    def active(self):
        """
        Filter Courses to those with CourseRuns that have not yet ended and are
        either open for enrollment or will be open for enrollment in the future.
        """
        now = datetime.datetime.now(pytz.UTC)
        return self.filter(
            (
                Q(course_runs__end__gt=now) |
                Q(course_runs__end__isnull=True)
            ) &
            (
                Q(course_runs__enrollment_end__gt=now) |
                Q(course_runs__enrollment_end__isnull=True)
            )
        )

    def marketable(self):
        """
        Filter Courses to those with CourseRuns that can be marketed. A CourseRun
        is deemed marketable if it has a defined slug, has seats, and has been published.
        """
        # exclude() is intentionally avoided here. We want Courses to be included
        # in the resulting queryset if only one of their runs matches our "marketable"
        # criteria. For example, consider a Course with two CourseRuns; one of the
        # runs is published while the other is not. If you used exclude(), the Course
        # would be dropped from the queryset even though it has one run which matches
        # our criteria.
        return self.filter(
            Q(course_runs__slug__isnull=False) & ~Q(course_runs__slug='')
        ).filter(
            course_runs__seats__isnull=False
        ).filter(
            course_runs__status=CourseRunStatus.Published
        ).distinct()


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
            (
                Q(end__gt=now) |
                Q(end__isnull=True)
            ) & (
                Q(enrollment_end__gt=now) |
                Q(enrollment_end__isnull=True)
            )
        )

    def enrollable(self):
        """ Returns course runs that are currently open for enrollment.

        A course run is considered open for enrollment if its enrollment start date
        has passed, is now or is None, AND its enrollment end date is in the future or is None.

        Returns:
            QuerySet
        """
        now = datetime.datetime.now(pytz.UTC)
        return self.filter(
            (
                Q(enrollment_end__gt=now) |
                Q(enrollment_end__isnull=True)
            ) & (
                Q(enrollment_start__lte=now) |
                Q(enrollment_start__isnull=True)
            )

        )

    def marketable(self):
        """ Returns CourseRuns that can be marketed to learners.

         A CourseRun is considered marketable if it has a defined slug, has seats, and has been published.

         Returns:
            QuerySet
         """

        return self.exclude(
            slug__isnull=True
        ).exclude(
            slug=''
        ).exclude(
            # This will exclude any course run without seats (e.g., CCX runs).
            seats__isnull=True
        ).filter(
            status=CourseRunStatus.Published
        )


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
