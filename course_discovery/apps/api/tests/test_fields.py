from django.test import TestCase

from course_discovery.apps.api.fields import ImageField


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
