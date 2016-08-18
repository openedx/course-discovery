import os

import ddt
from django.test import TestCase

from course_discovery.apps.course_metadata.tests.factories import ProgramFactory
from course_discovery.apps.course_metadata import utils


@ddt.ddt
class UploadToFieldNamePathTests(TestCase):
    """
    Test the utiltity object 'UploadtoFieldNamePath'
    """
    def setUp(self):
        super(UploadToFieldNamePathTests, self).setUp()
        self.program = ProgramFactory()

    @ddt.data(
        ('/media/program', 'uuid', '.jpeg'),
        ('/media/program', 'title', '.jpeg'),
        ('/media', 'uuid', '.jpeg'),
        ('/media', 'title', '.txt'),
        ('', 'title', ''),
    )
    @ddt.unpack
    def test_upload_to(self, path, field, ext):
        upload_to = utils.UploadToFieldNamePath(populate_from=field, path=path)
        upload_path = upload_to(self.program, 'name' + ext)
        expected = os.path.join(path, str(getattr(self.program, field)) + ext)
        self.assertEqual(upload_path, expected)
