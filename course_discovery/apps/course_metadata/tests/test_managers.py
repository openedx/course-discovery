import pytest
from django.db import models
from django.test import TestCase

from course_discovery.apps.course_metadata.models import CourseRun
from course_discovery.apps.course_metadata.tests.factories import CourseRunFactory


class DraftManagerTests(TestCase):
    def setUp(self):
        super().setUp()
        self.draft = CourseRunFactory(draft=True)
        self.nondraft = CourseRunFactory(draft=False, uuid=self.draft.uuid, key=self.draft.key,
                                         course=self.draft.course, draft_version=self.draft)

    def test_base_filter(self):
        """
        Verify the query set filters draft states out at a base level, not just by overriding all().
        """
        assert CourseRun.objects.count() == 1
        assert CourseRun.objects.first() == self.nondraft
        assert CourseRun.objects.last() == self.nondraft
        assert list(CourseRun.objects.all()) == [self.nondraft]

    def test_with_drafts(self):
        """
        Verify the query set allows access to draft rows too.
        """
        assert CourseRun._base_manager.count() == 2  # pylint: disable=protected-access
        assert CourseRun.objects._with_drafts().count() == 2  # pylint: disable=protected-access
        assert CourseRun.objects.count() == 1  # sanity check

    def test_filter_drafts(self):
        extra = CourseRunFactory()

        result = CourseRun.objects.filter_drafts()
        assert isinstance(result, models.QuerySet)
        assert result.count() == 2
        assert set(result) == {extra, self.draft}

    def test_filter_drafts_with_kwargs(self):
        extra = CourseRunFactory()

        result = CourseRun.objects.filter_drafts(course=extra.course)
        assert result.count() == 1
        assert result.first() == extra

    def test_get_draft(self):
        extra = CourseRunFactory(course=self.draft.course)

        with pytest.raises(CourseRun.DoesNotExist):
            CourseRun.objects.get_draft(hidden=True)
        with pytest.raises(CourseRun.MultipleObjectsReturned):
            CourseRun.objects.get_draft(course=extra.course)
        assert CourseRun.objects.get_draft(uuid=self.draft.uuid) == self.draft
