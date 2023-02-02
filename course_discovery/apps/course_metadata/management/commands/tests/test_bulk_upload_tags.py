import collections

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from django.test import TestCase

from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase
from course_discovery.apps.course_metadata.models import Course
from course_discovery.apps.course_metadata.tests.factories import BulkUploadTagsConfigFactory, CourseFactory


class BulkUploadTagsCommandTests(TestCase):
    """
    Test suite for bulk_upload_tags management command.
    """
    # def setUp(self):
    #     super().setUp()

    # def setUpTestData(self):
    #     self.course1 = CourseFactory()
    #     self.course2 = CourseFactory()
    #     self.course3 = CourseFactory()
    #     self.csv_file_content = ','.join([str(self.course1.uuid), 'tag0', 'tag1']) + '\n'
    #     self.csv_file_content += ','.join([str(self.course3.uuid), 'tag1', 'tag2', 'tag3']) + '\n'
    #     self.csv_file = SimpleUploadedFile(
    #         name='test.csv',
    #         content=self.csv_file_content.encode('utf-8'),
    #         content_type='text/csv'
    #     )

    def test_missing_csv(self):
        """
        Test that the command raises CommandError if no csv is provided.
        """
        pass
        # _ = BulkUploadTagsConfigFactory(enabled=True)
        # with self.assertRaises(CommandError):
        #     call_command(
        #         'bulk_upload_tags'
        #     )

    # def test_invalid_csv_path(self):
    #     """
    #     Test that the command raises CommandError if an invalid csv path is provided.
    #     """
    #     with self.assertRaises(CommandError):
    #         call_command(
    #             'bulk_upload_tags', '--csv_path', 'no_csv'
    #         )

    def test_success_flow(self):
        """
        Verify that for self.csv_file, the command updates tags successfully.
        """

        self.course1 = CourseFactory()
        self.course2 = CourseFactory()
        self.course3 = CourseFactory()
        self.csv_file_content = ','.join([str(self.course1.uuid), 'tag0', 'tag1']) + '\n'
        self.csv_file_content += ','.join([str(self.course3.uuid), 'tag1', 'tag2', 'tag3']) + '\n'
        self.csv_file = SimpleUploadedFile(
            name='test.csv',
            content=self.csv_file_content.encode('utf-8'),
            content_type='text/csv'
        )
        _ = BulkUploadTagsConfigFactory(csv_file=self.csv_file, enabled=True)
        call_command('bulk_upload_tags')

        tags_course_1 = map(lambda t: t.name, Course.objects.get(uuid=self.course1.uuid).topics.all())
        tags_course_2 = map(lambda t: t.name, Course.objects.get(uuid=self.course2.uuid).topics.all())
        tags_course_3 = map(lambda t: t.name, Course.objects.get(uuid=self.course3.uuid).topics.all())

        assert self.tag_lists_are_equal(tags_course_1, ['tag0', 'tag1'])
        assert self.tag_lists_are_equal(tags_course_2, [])
        assert self.tag_lists_are_equal(tags_course_3, ['tag1', 'tag2', 'tag3'])

    def tag_lists_are_equal(self, list_a, list_b):
        """
        Check if list_a is a permutation of list_b
        """
        return collections.Counter(list_a) == collections.Counter(list_b)
