from django.test import TestCase

from course_discovery.apps.api.fields import ImageField, StdImageSerializerField
from course_discovery.apps.api.tests.test_serializers import make_request
from course_discovery.apps.core.tests.helpers import make_image_file
from course_discovery.apps.course_metadata.tests.factories import ProgramFactory


class ImageFieldTests(TestCase):
    def test_to_representation(self):
        value = 'https://example.com/image.jpg'
        expected = {
            'src': value,
            'description': None,
            'height': None,
            'width': None
        }
        self.assertEqual(ImageField().to_representation(value), expected)


# pylint: disable=no-member
class StdImageSerializerFieldTests(TestCase):
    def test_to_representation(self):
        request = make_request()
        # TODO Create test-only model to avoid unnecessary dependency on Program model.
        program = ProgramFactory(banner_image=make_image_file('test.jpg'))
        field = StdImageSerializerField()
        field._context = {'request': request}  # pylint: disable=protected-access

        expected = {
            size_key: {
                'url': '{}{}'.format(
                    'http://testserver',
                    getattr(program.banner_image, size_key).url
                ),
                'width': program.banner_image.field.variations[size_key]['width'],
                'height': program.banner_image.field.variations[size_key]['height']
            }
            for size_key in program.banner_image.field.variations
        }

        self.assertDictEqual(field.to_representation(program.banner_image), expected)
