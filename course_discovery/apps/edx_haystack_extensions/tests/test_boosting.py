import datetime
from unittest.mock import patch

import pytest
import pytz
from dateutil.relativedelta import relativedelta
from haystack.query import SearchQuerySet

from course_discovery.apps.course_metadata.models import CourseRun, Program, ProgramType
from course_discovery.apps.course_metadata.tests.factories import CourseRunFactory, ProgramFactory


@pytest.mark.django_db
@pytest.mark.usefixtures('haystack_default_connection')
class TestSearchBoosting:
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

    @pytest.mark.parametrize('program_type', ['MicroMasters', 'Professional Certificate'])
    def test_program_type_boosting(self, program_type):
        """Verify MicroMasters and Professional Certificate are boosted over XSeries."""
        ProgramFactory(type=ProgramType.objects.get(translations__name_t='XSeries'))
        test_record = ProgramFactory(type=ProgramType.objects.get(translations__name_t=program_type))

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
        assert int(test_record.start.timestamp()) == int(search_results[0].start.timestamp())

    @pytest.mark.parametrize(
        'has_enrollable_paid_seats,paid_seat_enrollment_end,expects_boost',
        [
            # Should not get boost if has_enrollable_paid_seats is False, has_enrollable_paid_seats
            # is None, or paid_seat_enrollment_end is in the past.
            (False, None, False),
            (None, None, False),
            (True, datetime.datetime.now(pytz.timezone('utc')) - datetime.timedelta(days=15), False),
            # Should get boost if has_enrollable_paid_seats is True and paid_seat_enrollment_end
            # is None or in the future.
            (True, None, True),
            (True, datetime.datetime.now(pytz.timezone('utc')) + datetime.timedelta(days=15), True),
        ]
    )
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

    @pytest.mark.parametrize(
        'enrollment_start,enrollment_end,expects_boost',
        [
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
        ]
    )
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

    now = datetime.datetime.now(pytz.timezone('utc'))
    one_day = relativedelta(days=1)
    one_month = relativedelta(months=1)
    two_months = relativedelta(months=2)
    three_months = relativedelta(months=3)
    six_months = relativedelta(months=6)
    one_week = relativedelta(days=7)
    two_weeks = relativedelta(days=14)
    one_year = relativedelta(years=1)
    thirteen_months = relativedelta(months=13)

    @pytest.mark.parametrize(
        'runadates, runbdates, pacing_type, boosted',
        [
            # Current Self Paced Course (A) vs Future Self Paced Course (B)
            ((now - one_month, now + one_month), (now + one_month, now + two_months), 'self_paced', 'a'),
            # Further Start Current Self Paced Course (A)
            # vs Closer Start Current Self Paced Course (B)
            ((now - two_months, now + one_month), (now - one_month, now + two_months), 'self_paced', 'b'),
            # Closer Start Future Self Paced Course (A)
            # vs Further Start Future Self Paced Course (B)
            ((now + one_month, now + one_year), (now + two_months, now + thirteen_months), 'self_paced', 'a'),
            # Current Self Paced Course (A) that ends in two weeks
            # vs Future Self Paced Course that starts in two weeks (B)
            ((now - six_months, now + two_weeks), (now + two_weeks, now + six_months), 'self_paced', 'a'),
            # Current Instructor Paced Course that ends in one week (A)
            # vs Future Instructor Paced Course that starts in one day (B)
            ((now - six_months, now + one_week), (now + one_day, now + six_months), 'instructor_paced', 'b'),
            # Current Instructor Paced Course that ends in two weeks (A)
            # vs Future Instructor Paced Course that starts in one week (B)
            ((now - six_months, now + two_weeks), (now + one_week, now + six_months), 'instructor_paced', 'a'),
            # Future Instructor Paced Course that starts tomorrow (A)
            # vs Current Instructor Paced Course that is 2/3rds of the way done (B)
            ((now + one_day, now + six_months), (now - six_months, now + three_months), 'instructor_paced', 'b'),
        ]
    )
    def test_current_run_boosting(self, runadates, runbdates, pacing_type, boosted):
        """Verify that "current" CourseRuns are boosted.
        See the is_current_and_still_upgradeable CourseRun property to understand what this means."""

        (starta, enda) = runadates
        (startb, endb) = runbdates

        now = datetime.datetime.now(pytz.timezone('utc'))
        upgrade_deadline_tomorrow = now + relativedelta(days=1)

        with patch.object(CourseRun, 'get_paid_seat_enrollment_end', return_value=upgrade_deadline_tomorrow):
            runa = self.build_normalized_course_run(
                title='test1',
                start=starta,
                end=enda,
                pacing_type=pacing_type
            )
            runb = self.build_normalized_course_run(
                title='test2',
                start=startb,
                end=endb,
                pacing_type=pacing_type
            )
            search_results = SearchQuerySet().models(CourseRun).all()

        assert len(search_results) == 2
        if boosted == 'a':
            assert search_results[0].score > search_results[1].score
            assert runa.title == search_results[0].title
        else:
            assert search_results[0].score > search_results[1].score
            assert runb.title == search_results[0].title
