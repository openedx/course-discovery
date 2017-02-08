import datetime

import ddt
import pytz
from django.test import TestCase
from haystack.query import SearchQuerySet
from mock import patch

from course_discovery.apps.core.tests.mixins import ElasticsearchTestMixin
from course_discovery.apps.course_metadata.models import CourseRun, Program, ProgramType
from course_discovery.apps.course_metadata.tests.factories import CourseRunFactory, ProgramFactory


@ddt.ddt
class SearchBoostingTests(ElasticsearchTestMixin, TestCase):
    def build_normalized_course_run(self, **kwargs):
        """ Builds a CourseRun with fields set to normalize boosting behavior."""
        defaults = {
            'pacing_type': 'instructor_paced',
            'start': datetime.datetime.now(pytz.timezone('utc')) + datetime.timedelta(weeks=52),
            'enrollment_start': datetime.datetime.now(pytz.timezone('utc')) + datetime.timedelta(weeks=50),
            'enrollment_end': None
        }
        defaults.update(kwargs)
        return CourseRunFactory(**defaults)

    def test_start_date_boosting(self):
        """ Verify upcoming courses are boosted over past courses."""
        now = datetime.datetime.now(pytz.timezone('utc'))
        self.build_normalized_course_run(start=now + datetime.timedelta(weeks=10))
        test_record = self.build_normalized_course_run(start=now + datetime.timedelta(weeks=1))

        search_results = SearchQuerySet().models(CourseRun).all()
        self.assertEqual(2, len(search_results))
        self.assertGreater(search_results[0].score, search_results[1].score)
        self.assertEqual(int(test_record.start.timestamp()), int(search_results[0].start.timestamp()))  # pylint: disable=no-member

    def test_self_paced_boosting(self):
        """ Verify that self paced courses are boosted over instructor led courses."""
        self.build_normalized_course_run(pacing_type='instructor_paced')
        test_record = self.build_normalized_course_run(pacing_type='self_paced')

        search_results = SearchQuerySet().models(CourseRun).all()
        self.assertEqual(2, len(search_results))
        self.assertGreater(search_results[0].score, search_results[1].score)
        self.assertEqual(test_record.pacing_type, search_results[0].pacing_type)

    @ddt.data(
        # Case 1: Should not get boost if has_enrollable_paid_seats is False, has_enrollable_paid_seats is None or
        #   paid_seat_enrollment_end is in the past.
        (False, None, False),
        (None, None, False),
        (True, datetime.datetime.now(pytz.timezone('utc')) - datetime.timedelta(days=15), False),

        # Case 2: Should get boost if has_enrollable_paid_seats is True and paid_seat_enrollment_end is None or
        #   in the future.
        (True, None, True),
        (True, datetime.datetime.now(pytz.timezone('utc')) + datetime.timedelta(days=15), True)
    )
    @ddt.unpack
    def test_enrollable_paid_seat_boosting(self, has_enrollable_paid_seats, paid_seat_enrollment_end, expects_boost):
        """ Verify that CourseRuns for which an unenrolled user may enroll and purchase a paid Seat are boosted."""

        # Create a control record (one that should never be boosted).
        with patch.object(CourseRun, 'has_enrollable_paid_seats', return_value=False):
            with patch.object(CourseRun, 'get_paid_seat_enrollment_end', return_value=None):
                self.build_normalized_course_run(title='test1')

        # Create the test record (may be boosted).
        with patch.object(CourseRun, 'has_enrollable_paid_seats', return_value=has_enrollable_paid_seats):
            with patch.object(CourseRun, 'get_paid_seat_enrollment_end', return_value=paid_seat_enrollment_end):
                test_record = self.build_normalized_course_run(title='test2')

        search_results = SearchQuerySet().models(CourseRun).all()
        self.assertEqual(2, len(search_results))
        if expects_boost:
            self.assertGreater(search_results[0].score, search_results[1].score)
            self.assertEqual(test_record.title, search_results[0].title)
        else:
            self.assertEqual(search_results[0].score, search_results[1].score)

    @ddt.data('MicroMasters', 'Professional Certificate')
    def test_program_type_boosting(self, program_type):
        """ Verify MicroMasters and Professional Certificate are boosted over XSeries."""
        ProgramFactory(type=ProgramType.objects.get(name='XSeries'))
        test_record = ProgramFactory(type=ProgramType.objects.get(name=program_type))

        search_results = SearchQuerySet().models(Program).all()
        self.assertEqual(2, len(search_results))
        self.assertGreater(search_results[0].score, search_results[1].score)
        self.assertEqual(str(test_record.type), str(search_results[0].type))

    @ddt.data(
        # Case 1: Should get boost if enrollment_start and enrollment_end unspecified.
        (None, None, True),

        # Case 2: Should get boost if enrollment_start unspecified and enrollment_end in future.
        (None, datetime.datetime.now(pytz.timezone('utc')) + datetime.timedelta(days=15), True),

        # Case 3: Should get boost if enrollment_start in past and enrollment_end unspecified.
        (datetime.datetime.now(pytz.timezone('utc')) - datetime.timedelta(days=15), None, True),

        # Case 4: Should get boost if enrollment_start in past and enrollment_end in future.
        (datetime.datetime.now(pytz.timezone('utc')) - datetime.timedelta(days=15),
         datetime.datetime.now(pytz.timezone('utc')) + datetime.timedelta(days=15),
         True),

        # Case 5: Should not get boost if enrollment_start in future.
        (datetime.datetime.now(pytz.timezone('utc')) + datetime.timedelta(days=15), None, False),

        # Case 5: Should not get boost if enrollment_end in past.
        (None, datetime.datetime.now(pytz.timezone('utc')) - datetime.timedelta(days=15), False),
    )
    @ddt.unpack
    def test_enrollable_course_run_boosting(self, enrollment_start, enrollment_end, expects_boost):
        """ Verify that enrollable CourseRuns are boosted."""
        # Create a control record that should never be boosted
        self.build_normalized_course_run(title='test1')

        # Create the test record
        test_record = self.build_normalized_course_run(
            title='test2',
            enrollment_start=enrollment_start,
            enrollment_end=enrollment_end
        )

        search_results = SearchQuerySet().models(CourseRun).all()
        self.assertEqual(2, len(search_results))
        if expects_boost:
            self.assertGreater(search_results[0].score, search_results[1].score)
            self.assertEqual(test_record.title, search_results[0].title)
        else:
            self.assertEqual(search_results[0].score, search_results[1].score)
