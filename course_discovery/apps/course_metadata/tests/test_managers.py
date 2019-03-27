from django.db import models
from django.test import TestCase

from course_discovery.apps.course_metadata.models import CourseRun
from course_discovery.apps.course_metadata.tests.factories import CourseRunFactory


class DraftManagerTests(TestCase):
    def setUp(self):
        self.draft = CourseRunFactory(draft=True)
        self.nondraft = CourseRunFactory(draft=False, uuid=self.draft.uuid, key=self.draft.key,
                                         course=self.draft.course)

    def test_base_filter(self):
        """
        Verify the query set filters draft states out at a base level, not just by overriding all().
        """
        self.assertEqual(CourseRun.objects.count(), 1)
        self.assertEqual(CourseRun.objects.first(), self.nondraft)
        self.assertEqual(CourseRun.objects.last(), self.nondraft)
        self.assertEqual(list(CourseRun.objects.all()), [self.nondraft])

    def test_with_drafts(self):
        """
        Verify the query set allows access to draft rows too.
        """
        self.assertEqual(CourseRun._base_manager.count(), 2)  # pylint: disable=protected-access
        self.assertEqual(CourseRun.objects.with_drafts().count(), 2)
        self.assertEqual(CourseRun.objects.count(), 1)  # sanity check

    def test_find_drafts(self):
        extra_draft = CourseRunFactory(draft=True)
        extra_nondraft = CourseRunFactory(draft=False)

        result = CourseRun.objects.find_drafts()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 3)
        self.assertEqual(set(result), {extra_draft, extra_nondraft, self.draft})

    def test_find_drafts_with_kwargs(self):
        extra = CourseRunFactory()

        result = CourseRun.objects.find_drafts(course=extra.course)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], extra)

    def test_find_drafts_ignores_draft_arg(self):
        result = CourseRun.objects.find_drafts(draft=False)
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0].draft)

    def test_filter_drafts(self):
        extra = CourseRunFactory()

        result = CourseRun.objects.filter_drafts()
        self.assertIsInstance(result, models.QuerySet)
        self.assertEqual(result.count(), 2)
        self.assertEqual(set(result), {extra, self.draft})

    def test_filter_drafts_with_kwargs(self):
        extra = CourseRunFactory()

        result = CourseRun.objects.filter_drafts(course=extra.course)
        self.assertEqual(result.count(), 1)
        self.assertEqual(result.first(), extra)

    def test_get_draft(self):
        extra = CourseRunFactory(course=self.draft.course)

        with self.assertRaises(CourseRun.DoesNotExist):
            CourseRun.objects.get_draft(hidden=True)
        with self.assertRaises(CourseRun.MultipleObjectsReturned):
            CourseRun.objects.get_draft(course=extra.course)
        self.assertEqual(CourseRun.objects.get_draft(uuid=self.draft.uuid), self.draft)
