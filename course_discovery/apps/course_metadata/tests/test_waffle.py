from django.test import TestCase
from waffle.testutils import override_switch

from course_discovery.apps.course_metadata.waffle import masters_course_mode_enabled


class CurriculumWaffleTests(TestCase):

    @override_switch('masters_course_mode_enabled', active=True)
    def test_masters_course_mode_enabled_true(self):
        self.assertTrue(masters_course_mode_enabled())

    @override_switch('masters_course_mode_enabled', active=False)
    def test_masters_course_mode_enabled_false(self):
        self.assertFalse(masters_course_mode_enabled())
