import ddt
import pytest
from bs4 import BeautifulSoup
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from django.test import TestCase

from course_discovery.apps.course_metadata.tests.factories import CourseFactory
from course_discovery.apps.tagging.models import CourseVertical, SubVertical, Vertical
from course_discovery.apps.tagging.tests.factories import (
    CourseVerticalFactory, SubVerticalFactory, UpdateCourseVerticalsConfigFactory, VerticalFactory
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
            row_content = f'{row["course"]},{row["vertical"]},{row["subvertical"]}\n'
            csv_file_content += row_content

        csv_file = SimpleUploadedFile(
            name='test.csv',
            content=csv_file_content.encode('utf-8'),
            content_type='text/csv'
        )
        return csv_file

    def assert_email_content(self, success_count, failure_count, failure_reasons=None):
        email = mail.outbox[0]
        soup = BeautifulSoup(email.body)

        table = soup.find('table', {'width': '50%'})
        rows = table.find_all('tr')

        assert len(rows) == 4
        assert 'Total' in rows[1].find('th').get_text()
        assert 'Success' in rows[2].find('th').get_text()
        assert 'Failure' in rows[3].find('th').get_text()
        assert f'{success_count + failure_count}' == rows[1].find('td').get_text()
        assert f'{success_count}' == rows[2].find('td').get_text()
        assert f'{failure_count}' == rows[3].find('td').get_text()

        if failure_reasons:
            assert 'Failures' in soup.find('h3').get_text()
            failures = soup.find_all('li')
            for i, (key, value) in enumerate(failure_reasons.items()):
                assert failures[i].get_text().startswith(f"[{key}]: {value}")
        else:
            assert soup.find('h3') is None

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
        assert self.course1.product_vertical.vertical == self.ai_vertical
        assert self.course1.product_vertical.sub_vertical == self.python_subvertical
        assert self.course2.product_vertical.vertical == self.literature_vertical
        assert self.course2.product_vertical.sub_vertical == self.kafka_subvertical
        assert CourseVertical.objects.count() == 2
        assert Vertical.objects.count() == 2
        assert SubVertical.objects.count() == 2
        self.assert_email_content(success_count=2, failure_count=0)

    def test_empty_subvertical(self):
        self.csv_data.pop()
        self.csv_data[0]['subvertical'] = ''
        csv = self.build_csv(self.csv_data)
        UpdateCourseVerticalsConfigFactory(enabled=True, csv_file=csv)
        call_command('update_course_verticals')

        assert self.course1.product_vertical.vertical == self.ai_vertical
        assert self.course1.product_vertical.sub_vertical is None
        assert not hasattr(self.course2, 'vertical')
        assert CourseVertical.objects.count() == 1
        self.assert_email_content(success_count=1, failure_count=0)

    def test_nonexistent_vertical(self):
        self.csv_data[0]["vertical"] = "Computer Science"
        csv = self.build_csv(self.csv_data)
        UpdateCourseVerticalsConfigFactory(enabled=True, csv_file=csv)
        call_command('update_course_verticals')

        assert not hasattr(self.course1, 'vertical')
        assert self.course2.product_vertical.vertical == self.literature_vertical
        assert self.course2.product_vertical.sub_vertical == self.kafka_subvertical
        assert CourseVertical.objects.count() == 1
        self.assert_email_content(
            success_count=1, failure_count=1, failure_reasons={f"{self.course1.key}": "ValueError"}
        )

    def test_inactive_vertical(self):
        self.literature_vertical.is_active = False
        self.literature_vertical.save()

        csv = self.build_csv(self.csv_data)
        UpdateCourseVerticalsConfigFactory(enabled=True, csv_file=csv)
        call_command('update_course_verticals')

        assert self.course1.product_vertical.vertical == self.ai_vertical
        assert self.course1.product_vertical.sub_vertical == self.python_subvertical
        assert not hasattr(self.course2, 'vertical')
        assert CourseVertical.objects.count() == 1
        self.assert_email_content(
            success_count=1, failure_count=1, failure_reasons={f"{self.course2.key}": "ValueError"}
        )

    def test_raises_error_if_config_disabled(self):
        with pytest.raises(CommandError):
            csv = self.build_csv(self.csv_data)
            UpdateCourseVerticalsConfigFactory(enabled=False, csv_file=csv)
            call_command("update_course_verticals")
