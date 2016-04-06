import datetime

import pytz
from django.db import models


class CourseQuerySet(models.QuerySet):
    def active(self):
        """ Filters Courses to those with CourseRuns that are either currently open for enrollment,
        or will be open for enrollment in the future. """

        return self.filter(course_runs__enrollment_end__gt=datetime.datetime.now(pytz.UTC))
