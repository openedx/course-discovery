from django.core.management import call_command
from django.test import TestCase

from course_discovery.apps.course_metadata.models import CourseRun
from course_discovery.apps.course_metadata.tests import factories


class DeduplicateCourseMetadataHistoryCommandTests(TestCase):
    """
    Test the deduplicate_course_metadata_history management command for *basic
    functionality*.  This is not inteded as an exhaustive test of deduplication logic,
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
        # update in addition to a create.

    def run_command(self, model_identifier):
        call_command('deduplicate_course_metadata_history', model_identifier)

    def test_normal_case(self):
        """
        Test the case where we have a random mix of creates and updates to several
        different CourseRun records.
        """
        # Induce a few history records:
        # - 2 updates for courserun1
        # - 0 updates for courserun2
        # - 3 updates for courserun3
        self.courserun1.save()
        self.courserun3.save()
        self.courserun1.save()
        self.courserun3.save()
        factories.CourseRunFactory()  # Toss in a fourth create to mix things up.
        self.courserun3.save()

        courserun1_count_initial = len(CourseRun.history.filter(id=self.courserun1.id).all())  # pylint: disable=no-member
        courserun2_count_initial = len(CourseRun.history.filter(id=self.courserun2.id).all())  # pylint: disable=no-member
        courserun3_count_initial = len(CourseRun.history.filter(id=self.courserun3.id).all())  # pylint: disable=no-member

        # Ensure that there are multiple history records for each course run.  For each
        # course run, there should be 2 (baseline) + the amount we added at the
        # beginning of this test.
        self.assertEqual(courserun1_count_initial, 2 + 2)
        self.assertEqual(courserun2_count_initial, 2 + 0)
        self.assertEqual(courserun3_count_initial, 2 + 3)

        self.run_command('course_metadata.CourseRun')

        courserun1_count_final = len(CourseRun.history.filter(id=self.courserun1.id).all())  # pylint: disable=no-member
        courserun2_count_final = len(CourseRun.history.filter(id=self.courserun2.id).all())  # pylint: disable=no-member
        courserun3_count_final = len(CourseRun.history.filter(id=self.courserun3.id).all())  # pylint: disable=no-member

        # Ensure that the only history records left are the 3 original creates.
        self.assertEqual(courserun1_count_final, 1)
        self.assertEqual(courserun2_count_final, 1)
        self.assertEqual(courserun3_count_final, 1)
