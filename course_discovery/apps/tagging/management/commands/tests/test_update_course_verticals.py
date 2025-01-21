import ddt
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from django.test import TestCase

from course_discovery.apps.course_metadata.tests.factories import CourseFactory
from course_discovery.apps.tagging.models import CourseVertical, Vertical, SubVertical
from course_discovery.apps.tagging.tests.factories import (
    CourseVerticalFactory, SubVerticalFactory, VerticalFactory, UpdateCourseVerticalsConfigFactory
)

@ddt.ddt
class UpdateCourseVerticalsCommandTests(TestCase):
    """
    Test suite for update_course_verticals management command.
    """
    def setUp(self):
        super().setUp()
        self.course1 = CourseFactory()
        self.course2 = CourseFactory()
        self.ai_vertical = VerticalFactory(name="AI & Data Science")
        self.literature_vertical = VerticalFactory(name="Literature")
        self.python_subvertical = SubVerticalFactory(name="Python", vertical=self.ai_vertical)
        self.kafka_subvertical = SubVerticalFactory(name="Kafkaesque", vertical=self.literature_vertical)

        self.csv_data = [
            {"course": self.course1.key, "vertical": "AI & Data Science", "subvertical": "Python"},
            {"course": self.course2.key, "vertical": "Literature", "subvertical": "Kafkaesque"},
        ]
    
    def build_csv(self, rows):
        csv_file_content = "course,vertical,subvertical\n"
        for row in rows:
            row_content = f"{row["course"]},{row["vertical"]},{row["subvertical"]}\n"
            csv_file_content += row_content

        csv_file = SimpleUploadedFile(
            name='test.csv',
            content=csv_file_content.encode('utf-8'),
            content_type='text/csv'
        )
        return csv_file

    @ddt.data(True, False)
    def test_success(self, has_existing_verticals):
        if has_existing_verticals:
            CourseVerticalFactory(
                course=self.course1, vertical=self.literature_vertical, sub_vertical=self.kafka_subvertical
            )
            CourseVerticalFactory(
                course=self.course2, vertical=self.ai_vertical, sub_vertical=self.python_subvertical
            )
            assert CourseVertical.objects.count() == 2
        else:
            assert CourseVertical.objects.count() == 0

        csv = self.build_csv(self.csv_data)
        UpdateCourseVerticalsConfigFactory(enabled=True, csv_file=csv)
        call_command('update_course_verticals')

        self.course1.refresh_from_db()
        self.course2.refresh_from_db()
        assert self.course1.vertical.vertical == self.ai_vertical
        assert self.course1.vertical.sub_vertical == self.python_subvertical
        assert self.course2.vertical.vertical == self.literature_vertical
        assert self.course2.vertical.sub_vertical == self.kafka_subvertical
        assert CourseVertical.objects.count() == 2
        assert Vertical.objects.count() == 2
        assert SubVertical.objects.count() == 2
    
    def test_empty_subvertical(self):
        self.csv_data.pop()
        self.csv_data[0]['subvertical'] = ''
        csv = self.build_csv(self.csv_data)
        UpdateCourseVerticalsConfigFactory(enabled=True, csv_file=csv)
        call_command('update_course_verticals')

        assert self.course1.vertical.vertical == self.ai_vertical
        assert self.course1.vertical.sub_vertical is None
        assert not hasattr(self.course2, 'vertical')
        assert CourseVertical.objects.count() == 1

    def test_nonexistent_vertical(self):
        self.csv_data[0]["vertical"] = "Computer Science"
        csv = self.build_csv(self.csv_data)
        UpdateCourseVerticalsConfigFactory(enabled=True, csv_file=csv)
        call_command('update_course_verticals')

        assert not hasattr(self.course1, 'vertical')
        assert self.course2.vertical.vertical == self.literature_vertical
        assert self.course2.vertical.sub_vertical == self.kafka_subvertical
        assert CourseVertical.objects.count() == 1

    def test_inactive_vertical(self):
        self.literature_vertical.is_active = False
        self.literature_vertical.save()

        csv = self.build_csv(self.csv_data)
        UpdateCourseVerticalsConfigFactory(enabled=True, csv_file=csv)
        call_command('update_course_verticals')

        assert self.course1.vertical.vertical == self.ai_vertical
        assert self.course1.vertical.sub_vertical == self.python_subvertical
        assert not hasattr(self.course2, 'vertical')
        assert CourseVertical.objects.count() == 1
