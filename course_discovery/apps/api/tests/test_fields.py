# pylint: disable=no-member
import base64

import ddt
from django.core.files.base import ContentFile
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


@ddt.ddt
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

    def test_to_internal_value(self):
        base64_header = "data:image/jpeg;base64,"
        base64_data = (
            "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAKBueIx4ZKCMgoy0qqC+8P//8Nzc8P/////////////////////"
            "/////////////////////////////////////2wBDAaq0tPDS8P///////////////////////////////////////////////////////"
            "///////////////////////wgARCADIAMgDASIAAhEBAxEB/8QAFwABAQEBAAAAAAAAAAAAAAAAAAECA//EABYBAQEBAAAAAAAAAAAAAAA"
            "AAAABAv/aAAwDAQACEAMQAAABwADU6ZMtZFujDQzNwzbowtMNCZ68gAAADTI1kLci3I1INMjTI0yNZAAAAAAAAAAAAAAABrOpQgACStQAl"
            "JrOoCUAACCyazpQgACDUWUSozrNKJQAAILJrOlGTUhAoClIsiCrZZQgACCyazSCgAALZRmiAtyjTJdIKyKiwAAACxQlEsAAAAAAAAAAAAA"
            "AAAAAAAAAAAAAAAAAAAAADcMtDLQy3DLpzDcMunMNwy6cwAABZTpEBQg3lC43g1Lk6cunM65sLz6cwAAAAAAAABQAAAAA/8QAIBAAAwABB"
            "AMBAQAAAAAAAAAAAAERQRAhMUACMEJwIP/aAAgBAQABBQL+ITabIhCEIJEIQhCE9Xz8rnOcZfHiYEZXOPTSl1pSlEylKUpS/gL7L7L7L7L"
            "7L/TYTdjQkNEIRaREJpCEXoXJlnkfL4M5Z4i5zkZz6FplmwuGUyPlC51u/e//xAAUEQEAAAAAAAAAAAAAAAAAAABw/9oACAEDAQE/ASn/x"
            "AAUEQEAAAAAAAAAAAAAAAAAAABw/9oACAECAQE/ASn/xAAUEAEAAAAAAAAAAAAAAAAAAACQ/9oACAEBAAY/Ahx//8QAJBAAAwABBAEEAwE"
            "AAAAAAAAAAAERMRAhMEEgQFFhcWBwwfD/2gAIAQEAAT8h8HKydh2CUwPuYUzlHCyUHA9uRUsmcMomOFaK1wLJ76HoHgjsLH/dn8mQ7D3Q9"
            "zDcSjEYjVC4FszMxkMZBZG66fUUKGVMMED6mYvgZ0yqQ9go+fxBZ4H6BizwP0JZ4H4QfIWeC+L0T4iz4UvGuEs6UvAtHquEs8r1XEvo6X9"
            "bLdkiwCJCEhErIKoYe5I6BqMoQ3sRo02HuSOgefPAdizIvyYeAeI/YzIw0lkPIfX2NGjYPPnkVW0qEZo67GWwdSDSobUFVt0HSQ0FS3p2V"
            "PsaQVW0e79HSopsVFKXSn//2gAMAwEAAgADAAAAEABMIOBEPCPCAAAEIAEIEEAAAAAAAAAAAAAAAAAAPP8A/wDwAIX/AP8A/wDD8/8A/wC"
            "DCpP/AP8A/wAPzQuBBS4D3/8A/DzpBAMAYIX+wyMAAAAYIU8J7f7AAAAQQUgEpAz7AAAAAAAAAAAAAAAEMMMEEMAMAAAAAsQIQo0YY8AAA"
            "AAAAAAA88cAA//EABwRAQADAAIDAAAAAAAAAAAAAAEAESAQMDFQYP/aAAgBAwEBPxD05h88mWGHkywly9GGD0DLly4/H//EABwRAQADAAI"
            "DAAAAAAAAAAAAAAEAESAQMDFQYP/aAAgBAgEBPxD07g5ckcHKZIypWnzgidCXKlSvkP/EACoQAQACAQIEBQUBAQEAAAAAAAEAESExQRAwU"
            "WEgcYGh4ZGxwdHwQGDx/9oACAEBAAE/EPBYOzt8x3PpGgv6S2l1HA3l2i6wFNoXNte3ep9EvT5l4lqmTmqlQRsZQnYdPmUi0vSCUmqmdQ9"
            "e0xiwTMXXpyBYO8RUbJ+4/wB9ZoekdD6R+Wh7B+Z7wj+PWbDGc/Wfg/MODgsxEVGyfuKyDGz/AGYwFXBrElSsZ87gIhTfXvBT2ACJSjt41"
            "Q1dS9msdL+IAsuefxAAV67/ABFQejK0FVF1gC7zOCyDzG1VG6N3eZOLuOgKA9ZfKsdL+JSU2LsghIu5iAHXvLaBUe135mOf+P0JUqVKlSp"
            "XA7R147TeVKlSpUqVKlTbNLkapv4jTk7Jpcg5m8CAVpKQVK05WyaXjWo2ZvM1LgrtxdTk7JpeBBGbXeXweAZmWIhmPB8jZNLg0inxXwEI+"
            "X2TSi0XNYTeb+J/swxMniqZr49kGm5nqRDZ478ThrBEzFtxpHgeC+kvFMtg1FvXlHA1m3A1/wAY8d+O1cp5RpDgsNeIWch5F8SHgC5ePET"
            "eP/HkEd5lq24NltMMOcYhJL14CFsEMBL1LhhN5m1XV/20uDpDSK+soRY3l9hYkSlOkFuy1BCXm/aXOq4KR05Ear1qWzdP1Prh1/8AJo+f7"
            "h9k/HGnDPuYF0DRte7Ajtt6+k1fP9TW8n7k+x+094/ea/40ZczOsQbFH39YEQ6+NAVmFRZC63iqltjLEY0iIsadJSBuWISs3LwNhNkaVGK"
            "Rs+IgtDMCx0ZaaM17RbT1ZXGhTcsRob+c2RpUdqf4wBVe3lOxv0lNz27fuXRceX0mbTpt53KUY26dv3KUeXQ6RGx7Hb+uCBXn+Ihuir7fM"
            "//Z"
        )
        base64_full = base64_header + base64_data

        expected = ContentFile(base64.b64decode(base64_data), name='tmp.jpeg')

        # assert that the data chunks are equal
        self.assertListEqual(
            list(StdImageSerializerField().to_internal_value(base64_full).chunks()),
            list(expected.chunks())
        )

    @ddt.data("", False, None, [])
    def test_to_internal_value_falsey(self, falsey_value):
        self.assertIsNone(StdImageSerializerField().to_internal_value(falsey_value))
