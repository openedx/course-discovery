import datetime
import logging

import pytz
from analyticsclient.client import Client

from course_discovery.apps.course_metadata.data_loaders import AbstractDataLoader
from course_discovery.apps.course_metadata.models import CourseRun

logger = logging.getLogger(__name__)


class AnalyticsAPIDataLoader(AbstractDataLoader):

    API_TIMEOUT = 120  # time in seconds

    def __init__(self, partner, api_url, max_workers=None, is_threadsafe=False):
        super().__init__(partner, api_url, max_workers, is_threadsafe)

        # uuid: {course, count, recent_count}
        self.course_dictionary = {}
        # uuid: {program, count, recent_count}
        self.program_dictionary = {}

        if not (self.partner.analytics_url and self.partner.analytics_token):
            msg = 'Analytics API credentials are not properly configured for Partner [{partner}]!'.format(
                partner=partner.short_code)
            raise Exception(msg)

    def analytics_api_client(self):
        analytics_api_client = Client(base_url=self.partner.analytics_url,
                                      auth_token=self.partner.analytics_token,
                                      timeout=self.API_TIMEOUT)

        return analytics_api_client

    def ingest(self):
        """ Load data for all course runs. """
        now = datetime.datetime.now(pytz.UTC)
        # We don't need a high level of precision - looking for ~6months of data
        six_months_ago = now - datetime.timedelta(days=180)
        course_summaries_response = self.analytics_api_client().course_summaries()
        course_run_summaries = course_summaries_response.course_summaries(recent_date=six_months_ago,
                                                                          fields=['course_id',
                                                                                  'count',
                                                                                  'recent_count_change'])

        for course_run_summary in course_run_summaries:
            self._process_course_run_summary(course_run_summary=course_run_summary)

        for course_dict in self.course_dictionary.values():
            self._process_course_enrollment_count(course_dict['course'],
                                                  course_dict['count'],
                                                  course_dict['recent_count'])

        for program_dict in self.program_dictionary.values():
            # Update program count
            program = program_dict['program']
            program.enrollment_count = program_dict['count']
            program.recent_enrollment_count = program_dict['recent_count']
            program.save(suppress_publication=True)
            logger.info(f'Updating program: {program.uuid}')

    def _process_course_run_summary(self, course_run_summary):
        # Get course run object from course run key
        course_run_key = course_run_summary['course_id']
        course_run_count = int(course_run_summary['count'])
        course_run_recent_count = int(course_run_summary['recent_count_change'])
        try:
            course_run = CourseRun.objects.get(key__iexact=course_run_key)
        except CourseRun.DoesNotExist:
            logger.info(f'Course run: [{course_run_key}] not found in DB.')
            return

        course = course_run.course
        # Update course run counts
        course_run.enrollment_count = course_run_count
        course_run.recent_enrollment_count = course_run_recent_count
        course_run.save(suppress_publication=True)

        # Add course run total to course total in dictionary
        if course.uuid in self.course_dictionary:
            self.course_dictionary[course.uuid]['count'] += course_run_count
            self.course_dictionary[course.uuid]['recent_count'] += course_run_recent_count
        else:
            self.course_dictionary[course.uuid] = {'course': course,
                                                   'count': course_run_count,
                                                   'recent_count': course_run_recent_count}

    def _process_course_enrollment_count(self, course, count, recent_count):
        # update course count
        course.enrollment_count = count
        course.recent_enrollment_count = recent_count
        course.save()

        # Add course count to program dictionary for all programs
        for program in course.programs.all():
            # add course total to program total in dictionary
            if program.uuid in self.program_dictionary:
                self.program_dictionary[program.uuid]['count'] += count
                self.program_dictionary[program.uuid]['recent_count'] += recent_count
            else:
                self.program_dictionary[program.uuid] = {'program': program,
                                                         'count': count,
                                                         'recent_count': recent_count}
