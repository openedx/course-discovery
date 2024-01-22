from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from django.test import TestCase

from course_discovery.apps.course_metadata.models import Course, Program
from course_discovery.apps.course_metadata.tests.factories import (
    BulkUploadTagsConfigFactory, CourseFactory, DegreeFactory, ProgramFactory
)


class BulkUploadTagsCommandTests(TestCase):
    """
    Test suite for bulk_upload_tags management command.
    """
    def setUp(self):
        super().setUp()
        self.test_tags1 = ['tag0', 'tag1', 'tag2', 'tag3']
        self.test_tags2 = ['tag5', 'tag6', 'tag7']

        self.course1 = CourseFactory()
        self.course2 = CourseFactory()
        self.course3 = CourseFactory()
        self.degree1 = DegreeFactory()
        self.degree2 = DegreeFactory()
        self.program1 = ProgramFactory()
        self.program2 = ProgramFactory()

        self.csv_file_content = self.write_csv_file_content()

        self.csv_file = SimpleUploadedFile(
            name='test.csv',
            content=self.csv_file_content.encode('utf-8'),
            content_type='text/csv'
        )

    def write_csv_file_content(self):
        """
        Write the csv file content to a file.
        """
        csv_file_content = ''
        # list of tuples containing (product_uuid, product type and tags)
        products_data = [
            (self.course1.uuid, 'course', self.test_tags1),
            (self.course3.uuid, 'course', self.test_tags2),
            (self.degree1.uuid, 'degree', self.test_tags1),
            (self.degree2.uuid, 'degree', self.test_tags2),
            (self.program1.uuid, 'program', self.test_tags1),
            (self.program2.uuid, 'program', self.test_tags2),
        ]

        for product_uuid, product_type, tags in products_data:
            csv_file_content += ','.join([str(product_uuid), product_type] + tags) + '\n'

        return csv_file_content

    def test_missing_csv(self):
        """
        Test that the command raises CommandError if no csv is provided.
        """
        _ = BulkUploadTagsConfigFactory.create(enabled=True)
        with self.assertRaises(CommandError):
            call_command(
                'bulk_upload_tags'
            )

    def test_invalid_csv_path(self):
        """
        Test that the command raises CommandError if an invalid csv path is provided.
        """
        with self.assertRaises(CommandError):
            call_command(
                'bulk_upload_tags', '--csv_path', 'no_csv'
            )

    def test_success_flow(self):
        """
        Verify that for self.csv_file, the command updates tags successfully.
        """
        _ = BulkUploadTagsConfigFactory.create(csv_file=self.csv_file, enabled=True)
        call_command('bulk_upload_tags')

        tags_course_1 = [t.name for t in Course.objects.get(uuid=self.course1.uuid).topics.all()]
        tags_course_2 = [t.name for t in Course.objects.get(uuid=self.course2.uuid).topics.all()]
        tags_course_3 = [t.name for t in Course.objects.get(uuid=self.course3.uuid).topics.all()]

        # Get the tags for the degree's corresponding program.
        tags_degree_1 = [t.name for t in Program.objects.get(uuid=self.degree1.uuid).labels.all()]
        tags_degree_2 = [t.name for t in Program.objects.get(uuid=self.degree2.uuid).labels.all()]

        tags_program_1 = [t.name for t in Program.objects.get(uuid=self.program1.uuid).labels.all()]
        tags_program_2 = [t.name for t in Program.objects.get(uuid=self.program2.uuid).labels.all()]

        # Verify that the tags are updated correctly.
        assert set(tags_course_1) == set(self.test_tags1)
        assert set(tags_course_2) == set()
        assert set(tags_course_3) == set(self.test_tags2)
        assert set(tags_degree_1) == set(self.test_tags1)
        assert set(tags_degree_2) == set(self.test_tags2)
        assert set(tags_program_1) == set(self.test_tags1)
        assert set(tags_program_2) == set(self.test_tags2)
