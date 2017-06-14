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
class TestSearchBoosting(ElasticsearchTestMixin, TestCase):
    def build_normalized_course_run(self, **kwargs):
        """Builds a CourseRun with fields set to normalize boosting behavior."""
        defaults = {
            'pacing_type': 'instructor_paced',
            'start': datetime.datetime.now(pytz.timezone('utc')) + datetime.timedelta(weeks=52),
            'enrollment_start': datetime.datetime.now(pytz.timezone('utc')) + datetime.timedelta(weeks=50),
            'enrollment_end': None,
            **kwargs
        }

        return CourseRunFactory(**defaults)

    def test_self_paced_boosting(self):
        """Verify that self paced courses are boosted over instructor led courses."""
        self.build_normalized_course_run(pacing_type='instructor_paced')
        test_record = self.build_normalized_course_run(pacing_type='self_paced')

        search_results = SearchQuerySet().models(CourseRun).all()
        assert len(search_results) == 2
        assert search_results[0].score > search_results[1].score
        assert test_record.pacing_type == search_results[0].pacing_type

    @ddt.data('MicroMasters', 'Professional Certificate')
    def test_program_type_boosting(self, program_type):
        """Verify MicroMasters and Professional Certificate are boosted over XSeries."""
        ProgramFactory(type=ProgramType.objects.get(name='XSeries'))
        test_record = ProgramFactory(type=ProgramType.objects.get(name=program_type))

        search_results = SearchQuerySet().models(Program).all()
        assert len(search_results) == 2
        assert search_results[0].score > search_results[1].score
        assert str(test_record.type) == str(search_results[0].type)

    def test_start_date_boosting(self):
        """Verify upcoming courses are boosted over past courses."""
        now = datetime.datetime.now(pytz.timezone('utc'))
        self.build_normalized_course_run(start=now + datetime.timedelta(weeks=10))
        test_record = self.build_normalized_course_run(start=now + datetime.timedelta(weeks=1))

        search_results = SearchQuerySet().models(CourseRun).all()
        assert len(search_results) == 2
        assert search_results[0].score > search_results[1].score
        assert int(test_record.start.timestamp()) == int(search_results[0].start.timestamp())  # pylint: disable=no-member

    @ddt.data(
        # Should not get boost if has_enrollable_paid_seats is False, has_enrollable_paid_seats
        # is None, or paid_seat_enrollment_end is in the past.
        (False, None, False),
        (None, None, False),
        (True, datetime.datetime.now(pytz.timezone('utc')) - datetime.timedelta(days=15), False),
        # Should get boost if has_enrollable_paid_seats is True and paid_seat_enrollment_end
        # is None or in the future.
        (True, None, True),
        (True, datetime.datetime.now(pytz.timezone('utc')) + datetime.timedelta(days=15), True),
    )
    @ddt.unpack
    def test_enrollable_paid_seat_boosting(self, has_enrollable_paid_seats, paid_seat_enrollment_end, expects_boost):
        """
        Verify that CourseRuns for which an unenrolled user may enroll and
        purchase a paid Seat are boosted.
        """

        # Create a control record (one that should never be boosted).
        with patch.object(CourseRun, 'has_enrollable_paid_seats', return_value=False):
            with patch.object(CourseRun, 'get_paid_seat_enrollment_end', return_value=None):
                self.build_normalized_course_run(title='test1')

        # Create the test record (may be boosted).
        with patch.object(CourseRun, 'has_enrollable_paid_seats', return_value=has_enrollable_paid_seats):
            with patch.object(CourseRun, 'get_paid_seat_enrollment_end', return_value=paid_seat_enrollment_end):
                test_record = self.build_normalized_course_run(title='test2')

        search_results = SearchQuerySet().models(CourseRun).all()
        assert len(search_results) == 2

        if expects_boost:
            assert search_results[0].score > search_results[1].score
            assert test_record.title == search_results[0].title
        else:
            assert search_results[0].score == search_results[1].score

    def test_expired_paid_seat_penalized(self):
        """
        Verify that a course run with an expired, paid seat is penalized relative
        to one with an enrollable, paid seat.
        """
        now = datetime.datetime.now(pytz.timezone('utc'))

        future = now + datetime.timedelta(days=15)
        with patch.object(CourseRun, 'has_enrollable_paid_seats', return_value=True):
            with patch.object(CourseRun, 'get_paid_seat_enrollment_end', return_value=future):
                promoted_run = self.build_normalized_course_run(title='promoted')

        past = now - datetime.timedelta(days=15)
        with patch.object(CourseRun, 'has_enrollable_paid_seats', return_value=True):
            with patch.object(CourseRun, 'get_paid_seat_enrollment_end', return_value=past):
                penalized_run = self.build_normalized_course_run(title='penalized')

        search_results = SearchQuerySet().models(CourseRun).all()
        assert len(search_results) == 2

        assert [promoted_run.title, penalized_run.title] == [hit.title for hit in search_results]
        assert search_results[0].score > search_results[1].score

        # Verify that this result has a negative score. Course runs with expired,
        # paid seats are penalized by having a relatively large value subtracted
        # from their relevance score. In this test case, the result should be a
        # negative relevance score.
        assert 0 > search_results[1].score

    @ddt.data(
        # Should get boost if enrollment_start and enrollment_end unspecified.
        (None, None, True),
        # Should get boost if enrollment_start unspecified and enrollment_end in future.
        (None, datetime.datetime.now(pytz.timezone('utc')) + datetime.timedelta(days=15), True),
        # Should get boost if enrollment_start in past and enrollment_end unspecified.
        (datetime.datetime.now(pytz.timezone('utc')) - datetime.timedelta(days=15), None, True),
        # Should get boost if enrollment_start in past and enrollment_end in future.
        (
            datetime.datetime.now(pytz.timezone('utc')) - datetime.timedelta(days=15),
            datetime.datetime.now(pytz.timezone('utc')) + datetime.timedelta(days=15),
            True
        ),
        # Should not get boost if enrollment_start in future.
        (datetime.datetime.now(pytz.timezone('utc')) + datetime.timedelta(days=15), None, False),
        # Should not get boost if enrollment_end in past.
        (None, datetime.datetime.now(pytz.timezone('utc')) - datetime.timedelta(days=15), False),
    )
    @ddt.unpack
    def test_enrollable_course_run_boosting(self, enrollment_start, enrollment_end, expects_boost):
        """Verify that enrollable CourseRuns are boosted."""

        # Create a control record that should never be boosted
        self.build_normalized_course_run(title='test1')

        # Create the test record
        test_record = self.build_normalized_course_run(
            title='test2',
            enrollment_start=enrollment_start,
            enrollment_end=enrollment_end
        )

        search_results = SearchQuerySet().models(CourseRun).all()
        assert len(search_results) == 2

        if expects_boost:
            assert search_results[0].score > search_results[1].score
            assert test_record.title == search_results[0].title
        else:
            assert search_results[0].score == search_results[1].score
