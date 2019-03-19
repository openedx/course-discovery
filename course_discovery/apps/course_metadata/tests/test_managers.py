from django.test import TestCase

from course_discovery.apps.course_metadata.models import CourseRun
from course_discovery.apps.course_metadata.tests.factories import CourseRunFactory


class DraftManagerTests(TestCase):
    def test_base_filter(self):
        """
        Verify the query set filters draft states out at a base level, not just by overriding all().
        """
        CourseRunFactory(draft=True)
        nondraft = CourseRunFactory(draft=False)

        self.assertEqual(CourseRun.objects.count(), 1)
        self.assertEqual(CourseRun.objects.first(), nondraft)
        self.assertEqual(CourseRun.objects.last(), nondraft)
        self.assertEqual(list(CourseRun.objects.all()), [nondraft])

    def test_with_drafts(self):
        """
        Verify the query set allows access to draft rows too.
        """
        CourseRunFactory(draft=True)
        CourseRunFactory(draft=False)

        self.assertEqual(CourseRun._base_manager.count(), 2)  # pylint: disable=protected-access
        self.assertEqual(CourseRun.objects.with_drafts().count(), 2)
        self.assertEqual(CourseRun.objects.count(), 1)  # sanity check
