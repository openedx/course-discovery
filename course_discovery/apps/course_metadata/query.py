import datetime

import pytz
from django.db import models
from django.db.models.query_utils import Q

from course_discovery.apps.course_metadata.choices import CourseRunStatus, ProgramStatus


class CourseQuerySet(models.QuerySet):
    def available(self):
        """
        A Course is considered to be "available" if it contains at least one CourseRun
        that can be enrolled in immediately, is ongoing or yet to start, and appears
        on the marketing site.
        """
        now = datetime.datetime.now(pytz.UTC)

        # A CourseRun is "enrollable" if its enrollment start date has passed,
        # is now, or is None, and its enrollment end date is in the future or is None.
        enrollable = (
            (
                Q(course_runs__enrollment_start__lte=now) |
                Q(course_runs__enrollment_start__isnull=True)
            ) &
            (
                Q(course_runs__enrollment_end__gt=now) |
                Q(course_runs__enrollment_end__isnull=True)
            )
        )

        # A CourseRun is "not ended" if its end date is in the future or is None.
        not_ended = (
            Q(course_runs__end__gt=now) | Q(course_runs__end__isnull=True)
        )

        # A CourseRun is "marketable" if it has a non-empty slug, has seats, and
        # is has a "published" status.
        marketable = (
            ~Q(course_runs__slug='') &
            Q(course_runs__seats__isnull=False) &
            Q(course_runs__draft=False) &
            ~Q(course_runs__type__is_marketable=False) &
            Q(course_runs__status=CourseRunStatus.Published)
        )

        # exclude() is intentionally avoided here. We want Courses to be included
        # in the resulting queryset if at least one of their runs matches our availability
        # criteria. For example, consider a Course with two CourseRuns; one of the
        # runs is published while the other is not. If you used exclude(), the Course
        # would be dropped from the queryset even though it has one run which matches
        # our availability criteria.

        # By itself, the query performs a join across several tables and would return
        # the id of the same course multiple times (a separate copy for each available
        # seat in each available run).
        ids = self.filter(enrollable & not_ended & marketable).values('id').distinct()

        # Now return the full object for each of the selected ids
        return self.filter(id__in=ids)


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
            slug=''
        ).exclude(
            # This will exclude any course run without seats (e.g., CCX runs).
            seats__isnull=True
        ).filter(
            draft=False
        ).exclude(
            type__is_marketable=False
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
