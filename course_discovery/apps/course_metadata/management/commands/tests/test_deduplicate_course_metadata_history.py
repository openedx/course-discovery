from django.core.management import CommandError, call_command
from django.test import TestCase

from course_discovery.apps.course_metadata.models import CourseRun, DeduplicateHistoryConfig
from course_discovery.apps.course_metadata.tests import factories


class DeduplicateCourseMetadataHistoryCommandTests(TestCase):
    """
    Test the deduplicate_course_metadata_history management command for *basic
    functionality*.  This is not intended as an exhaustive test of deduplication logic,
    which is already tested upstream (django-simple-history).  The goal is to test for
    possible regressions caused by changes in upstream's API, and to make sure the
    management command launches correctly.
    """
    def setUp(self):
        super().setUp()
        self.courserun1 = factories.CourseRunFactory(draft=False)
        self.courserun2 = factories.CourseRunFactory(draft=False)
        self.courserun3 = factories.CourseRunFactory(draft=True)

        # At this point, there are 6 total history records: three creates and
        # three updates.  The CourseRunFactory is apparently responsible for an
        # update in addition to a creation.

    def run_command(self, model_identifier):
        call_command('deduplicate_course_metadata_history', model_identifier)

    def _assert_normal_case_pre_command(self):
        """
        Verify the history count before running the clean-up command.
        """
        self.courserun1.title = 'test title'
        self.courserun1.save()

        self.courserun3.title = 'test title'
        self.courserun3.save()

        self.courserun1.title = 'test title again'
        self.courserun1.save()

        self.courserun3.title = 'test title again'
        self.courserun3.save()
        factories.CourseRunFactory()  # Toss in a fourth create to mix things up.
        self.courserun3.save()

        courserun1_count_initial = CourseRun.history.filter(id=self.courserun1.id).count()  # pylint: disable=no-member
        courserun2_count_initial = CourseRun.history.filter(id=self.courserun2.id).count()  # pylint: disable=no-member
        courserun3_count_initial = CourseRun.history.filter(id=self.courserun3.id).count()  # pylint: disable=no-member

        # Ensure that there are multiple history records for each course run.  For each
        # course run, there should be 2 (baseline) + the amount we added at the
        # beginning of this test * 2 for the double save for enterprise inclusion boolean
        assert courserun1_count_initial == 3
        assert courserun2_count_initial == 1
        assert courserun3_count_initial == 3

    def _assert_normal_case_post_command(self):
        """
        Verify the history count after duplicate cleanup command.
        """
        courserun1_count_final = CourseRun.history.filter(id=self.courserun1.id).count()  # pylint: disable=no-member
        courserun2_count_final = CourseRun.history.filter(id=self.courserun2.id).count()  # pylint: disable=no-member
        courserun3_count_final = CourseRun.history.filter(id=self.courserun3.id).count()  # pylint: disable=no-member

        # Ensure that the only history records left are the 3 original creates.
        # count remains same because all history instances are unique.
        assert courserun1_count_final == 3
        assert courserun2_count_final == 1
        assert courserun3_count_final == 3

    def test_normal_case(self):
        """
        Test the case where we have a random mix of creates and updates to several CourseRun records.
        """
        self._assert_normal_case_pre_command()
        self.run_command('course_metadata.CourseRun')
        self._assert_normal_case_post_command()

    def test_args_from_database(self):
        """
        Verify the configuration  is read  from database config model if --args-from-database is provided.
        """
        config = DeduplicateHistoryConfig.get_solo()
        config.arguments = 'course_metadata.CourseRun'
        config.save()

        self._assert_normal_case_pre_command()
        call_command('deduplicate_course_metadata_history', '--args-from-database')
        self._assert_normal_case_post_command()

    def test_command_error__missing_arguments(self):
        """
        Verify the deduplication command raises CommandError if neither args-from-database, auto, nor models arguments
        are provided.
        """
        with self.assertRaisesMessage(
                CommandError, "Either args_from_database, auto or models must be provided."
        ):
            call_command('deduplicate_course_metadata_history')
