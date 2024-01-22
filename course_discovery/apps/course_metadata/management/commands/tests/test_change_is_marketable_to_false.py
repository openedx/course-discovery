from django.core.management import call_command
from django.test import TestCase

from course_discovery.apps.course_metadata.models import CourseRunType
from course_discovery.apps.course_metadata.tests.factories import CourseRunTypeFactory


class ChangeIsMarketableToCourseRunTypesCommandTests(TestCase):
    def setUp(self):
        super().setUp()
        self.course_run_type_1 = CourseRunTypeFactory()
        self.course_run_type_2 = CourseRunTypeFactory()
        self.course_run_type_3 = CourseRunTypeFactory()

    def testNormalRunCommand(self):
        call_command('change_is_marketable_to_false')
        assert CourseRunType.objects.filter(uuid=self.course_run_type_1.uuid).exists()
        assert CourseRunType.objects.get(uuid=self.course_run_type_1.uuid).is_marketable is False
        assert CourseRunType.objects.filter(uuid=self.course_run_type_2.uuid).exists()
        assert CourseRunType.objects.get(uuid=self.course_run_type_2.uuid).is_marketable is False
        assert CourseRunType.objects.filter(uuid=self.course_run_type_3.uuid).exists()
        assert CourseRunType.objects.get(uuid=self.course_run_type_3.uuid).is_marketable is False
