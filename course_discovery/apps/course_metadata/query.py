import datetime

import pytz
from django.db import models
from django.db.models.query_utils import Q


class CourseQuerySet(models.QuerySet):
    def active(self):
        """ Filters Courses to those with CourseRuns that are either currently open for enrollment,
        or will be open for enrollment in the future. """

        return self.filter(
            Q(course_runs__end__gt=datetime.datetime.now(pytz.UTC)) &
            (
                Q(course_runs__enrollment_end__gt=datetime.datetime.now(pytz.UTC)) |
                Q(course_runs__enrollment_end__isnull=True)
            )
        )
