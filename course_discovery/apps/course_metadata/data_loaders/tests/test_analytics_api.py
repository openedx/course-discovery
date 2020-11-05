import json

import responses
from django.test import TestCase

from course_discovery.apps.course_metadata.data_loaders.analytics_api import AnalyticsAPIDataLoader
from course_discovery.apps.course_metadata.data_loaders.tests import JSON, mock_data
from course_discovery.apps.course_metadata.data_loaders.tests.mixins import DataLoaderTestMixin
from course_discovery.apps.course_metadata.models import Course, CourseRun, Program
from course_discovery.apps.course_metadata.tests.factories import CourseFactory, CourseRunFactory, ProgramFactory


class AnalyticsAPIDataLoaderTests(DataLoaderTestMixin, TestCase):
    @property
    def api_url(self):
        return self.partner.analytics_url

    loader_class = AnalyticsAPIDataLoader
    mocked_data = mock_data.ANALYTICS_API_COURSE_SUMMARIES_BODIES

    def _define_course_metadata(self):
        # Add course runs, courses, and programs to DB to copy data into
        courses = {}
        # Course runs map to courses in the way opaque keys would (without actually using opaque keys code)
        course_to_run_mapping = {
            '00test/00test/00test': '00test/00test',
            '00test/00test/01test': '00test/00test',
            '00test/01test/00test': '00test/01test',
            '00test/01test/01test': '00test/01test',
            '00test/01test/02test': '00test/01test',
            '00test/02test/00test': '00test/02test'
        }
        for course_summary in self.mocked_data:
            course_run_key = course_summary['course_id']
            course_key = course_to_run_mapping[course_run_key]
            if course_key in courses:
                course = courses[course_key]
                course_run = CourseRunFactory(key=course_summary['course_id'], course=course)
                course_run.save()
            else:
                course = CourseFactory(key=course_key)
                course.save()
                course_run = CourseRunFactory(key=course_summary['course_id'], course=course)
                course_run.save()
                courses[course_key] = course_run.course

        # Create a program with all of the courses we created
        program = ProgramFactory()
        program.courses.set(courses.values())

    @responses.activate
    def test_ingest(self):
        self._define_course_metadata()

        url = f'{self.api_url}course_summaries/'
        responses.add(
            method=responses.GET,
            url=url,
            body=json.dumps(self.mocked_data),
            match_querystring=False,
            content_type=JSON
        )
        self.loader.ingest()

        # For runs, let's just confirm that enrollment counts were recorded and add up counts for courses
        expected_course_enrollment_counts = {}
        course_runs = CourseRun.objects.all()
        for course_run in course_runs:
            self.assertGreater(course_run.enrollment_count, 0)
            self.assertGreater(course_run.recent_enrollment_count, 0)
            course = course_run.course
            if course.key in expected_course_enrollment_counts.keys():
                expected_course_enrollment_counts[course.key]['count'] += course_run.enrollment_count
                expected_course_enrollment_counts[course.key]['recent_count'] += course_run.recent_enrollment_count
            else:
                expected_course_enrollment_counts[course.key] = {'count': course_run.enrollment_count,
                                                                 'recent_count': course_run.recent_enrollment_count}

        # For courses, let's confirm that the course math is right in the ingest method and add courses for programs
        expected_program_enrollment_count = 0
        expected_program_recent_enrollment_count = 0
        courses = Course.objects.all()
        for course in courses:
            expected_counts = expected_course_enrollment_counts[course.key]
            expected_program_enrollment_count += expected_counts['count']
            expected_program_recent_enrollment_count += expected_counts['recent_count']
            self.assertEqual(course.enrollment_count, expected_counts['count'])
            self.assertEqual(course.recent_enrollment_count, expected_counts['recent_count'])
        courses = Course.objects.all()

        # For programs, let's confirm that the program math is right in the ingest method
        programs = Program.objects.all()
        self.assertEqual(programs[0].enrollment_count, expected_program_enrollment_count)
        self.assertEqual(programs[0].recent_enrollment_count, expected_program_recent_enrollment_count)
